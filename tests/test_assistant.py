"""Native protocol tests: real PostgreSQL; PeopleWelcome HTTP doubles ONLY here."""
import json
from datetime import timedelta

import httpx
import pytest
import respx
from sqlalchemy import func, select

from nebula.config import settings
from nebula.db import transaction
from nebula.models import AssistantTurn, Audit, Instance, PeopleWelcomeConnection, User, now
from nebula.security import cipher

TOKEN = 'test-only-zitadel-access-token'
AI = 'owned-active-character'


@pytest.fixture
def provider(client):
    base = settings().peoplewelcome_api_url
    with respx.mock as router:
        identity = router.get(settings().peoplewelcome_issuer+'/oidc/v1/userinfo').respond(200,json={'sub':'customer-zitadel-subject'})
        mine = router.get(base+'/api/v1/ais/mine').respond(200,json={'ais':[
            {'id':AI,'name':'Nebula Support','lifecycle':'active','model':'openai'},
            {'id':'not-ready','name':'Pending','lifecycle':'pending','model':'openai'},
            {'id':'other-provider','name':'Other','lifecycle':'active','model':'unchained'}]})
        conversation = router.get(base+'/api/v1/conversations',params={'ai_ids':AI}).respond(200,json={'messages':[
            {'id':'old-reply','role':'assistant','content':'A previous answer.'}]})
        submit = router.post(base+'/api/v1/agent/chat').respond(202,json={'conversation_id':'conv-1','job':{'id':'job-1','status':'queued'}})
        job = router.get(base+'/api/v1/jobs/job-1').respond(200,json={'job':{'id':'job-1','status':'running'}})
        response=client.post('/api/v1/assistant/connection',json={'access_token':TOKEN,'ai_id':AI})
        assert response.status_code==200,response.text
        yield {'identity':identity,'mine':mine,'conversation':conversation,'submit':submit,'job':job}


def due(turn_id):
    with transaction() as db:
        db.get(AssistantTurn,turn_id).next_poll_at=now()-timedelta(seconds=1)


def send(client,message='Show my instances and usage',key='support-request-one'):
    return client.post('/api/v1/assistant/messages',json={'message':message},headers={'Idempotency-Key':key})


def test_native_chat_scoped_context_and_queued_replies(client,customer,provider):
    uid,pid,rid=customer
    with transaction() as db:
        other=User(email='other@example.com',password_hash='unused');db.add(other);db.flush()
        from nebula.models import Project
        project=Project(user_id=other.id,provider_id='foreign-tenant',auth_url='https://invalid',credential='FOREIGN_SECRET');db.add(project);db.flush()
        db.add_all([Instance(project_id=pid,name='customer-vm',request={},rate_id=rid,vcpus=2,ram_mb=4096,disk_gb=10,state='ACTIVE'),
            Instance(project_id=project.id,name='FOREIGN_VM',request={},rate_id=rid,vcpus=1,ram_mb=1,disk_gb=1)])
    first=send(client)
    assert first.status_code==202,first.text
    turn_id=first.json()['id']
    payload=json.loads(provider['submit'].calls[0].request.content)
    assert set(payload)=={'ai_ids','message','train_memory'}
    assert payload['train_memory'] is False and payload['ai_ids']==[AI]
    assert 'customer-vm' in payload['message'] and 'settled_usage_micro_usd' in payload['message']
    for private in ['FOREIGN_VM','FOREIGN_SECRET','test-only-secret','scoped-test-id',TOKEN]:
        assert private not in payload['message']
    assert provider['submit'].calls[0].request.headers['Authorization']=='Bearer '+TOKEN
    assert send(client).json()['id']==turn_id and provider['submit'].call_count==1
    assert send(client,message='changed').status_code==409
    assert send(client,key='second-turn-key').status_code==409
    assert client.get('/api/v1/assistant/messages/'+turn_id).json()['status']=='queued'
    assert provider['job'].call_count==0  # minimum polling interval
    due(turn_id)
    assert client.get('/api/v1/assistant/messages/'+turn_id).json()['status']=='running'
    provider['job'].respond(200,json={'job':{'id':'job-1','status':'succeeded'}})
    provider['conversation'].respond(200,json={'messages':[
        {'id':'old-reply','role':'assistant','content':'A previous answer.'},
        {'id':'question','role':'user','content':payload['message']},
        {'id':'reply','role':'assistant','ai_name':'Nebula Support','content':'Your VM is active. <script>untrusted</script>','conversation_id':'conv-1'},
        {'id':'wrong-conversation','role':'assistant','content':'not this conversation','conversation_id':'foreign'}]})
    due(turn_id)
    result=client.get('/api/v1/assistant/messages/'+turn_id).json()
    assert result['status']=='succeeded' and [r['id'] for r in result['replies']]==['reply']
    assert result['access']=='read-only'
    assert client.get('/api/v1/assistant/messages/not-owned').status_code==404
    with transaction() as db:
        stored=db.get(PeopleWelcomeConnection,uid)
        assert TOKEN not in stored.credential and cipher().decrypt(stored.credential.encode()).decode()==TOKEN
        assert db.scalar(select(func.count()).select_from(AssistantTurn))==1
        assert TOKEN not in json.dumps([a.detail for a in db.scalars(select(Audit))])


def test_timeout_retry_retains_frozen_payload_and_upstream_key(client,customer,provider):
    provider['submit'].side_effect=httpx.ReadTimeout('sensitive provider body '+TOKEN)
    response=send(client)
    assert response.status_code==502 and TOKEN not in response.text
    with transaction() as db:
        turn=db.scalar(select(AssistantTurn));turn_id=turn.id
        original=turn.payload
        db.get(User,customer[0]).balance=999999
    # GET never resubmits a model call, including prepared intents.
    due(turn_id)
    assert client.get('/api/v1/assistant/messages/'+turn_id).json()['status']=='prepared'
    assert provider['submit'].call_count==1
    provider['submit'].side_effect=None
    provider['submit'].respond(202,json={'conversation_id':'conv-1','job':{'id':'job-1'}})
    response=client.post('/api/v1/assistant/messages/'+turn_id+'/resume')
    assert response.status_code==202,response.text
    requests=provider['submit'].calls
    assert requests[0].request.headers['Idempotency-Key']==requests[1].request.headers['Idempotency-Key']
    assert json.loads(requests[1].request.content)==original
    assert provider['conversation'].call_count==1


def test_rate_limit_backoff_and_auth_renewal(client,provider):
    provider['submit'].respond(429,headers={'Retry-After':'30'},text=TOKEN)
    response=send(client)
    assert response.status_code==429 and response.headers['Retry-After']=='30' and TOKEN not in response.text
    active=client.get('/api/v1/assistant/connection').json()['pending_turn_id']
    assert send(client).json()['status']=='prepared'
    assert provider['submit'].call_count==1
    due(active)
    provider['submit'].respond(401,text=TOKEN)
    response=client.post('/api/v1/assistant/messages/'+active+'/resume')
    assert response.status_code==424 and TOKEN not in response.text
    renewed=client.post('/api/v1/assistant/connection',json={'access_token':TOKEN+'-renewed','ai_id':AI})
    assert renewed.status_code==200
    assert client.delete('/api/v1/assistant/connection').status_code==409
    due(active)
    provider['submit'].respond(202,json={'conversation_id':'conv-1','job':{'id':'job-1'}})
    assert client.post('/api/v1/assistant/messages/'+active+'/resume').status_code==202
    assert provider['submit'].calls[-1].request.headers['Authorization']=='Bearer '+TOKEN+'-renewed'


def test_connection_identity_exclusive_after_disconnect(client,customer,provider):
    response=client.post('/api/v1/assistant/connection',json={'access_token':TOKEN})
    assert response.json()['characters']==[{'id':AI,'name':'Nebula Support'}]
    assert client.post('/api/v1/assistant/connection',json={'access_token':TOKEN,'ai_id':'not-ready'}).status_code==422
    assert client.delete('/api/v1/assistant/connection').status_code==200
    assert client.get('/api/v1/assistant/connection').json()['connected'] is False
    from nebula.assistant import connect
    from fastapi import HTTPException
    with transaction() as db:
        other=User(email='different@example.com',password_hash='unused');db.add(other);db.flush();other_id=other.id
    with pytest.raises(HTTPException) as exc:
        connect(other_id,TOKEN,AI)
    assert exc.value.status_code==409
    provider['identity'].respond(200,json={'sub':'different-account'})
    assert client.post('/api/v1/assistant/connection',json={'access_token':TOKEN,'ai_id':AI}).status_code==409


def test_failed_job_displays_available_replies_and_never_executes_changes(client,provider):
    first=send(client,message='Delete all my VMs').json()
    due(first['id'])
    provider['job'].respond(200,json={'job':{'id':'job-1','status':'failed','error':TOKEN}})
    provider['conversation'].respond(200,json={'messages':[{'id':'partial','role':'assistant','content':'Use the dashboard to confirm deletion.'}]})
    result=client.get('/api/v1/assistant/messages/'+first['id'])
    assert result.json()['status']=='failed' and len(result.json()['replies'])==1
    assert TOKEN not in result.text
    from nebula.models import Operation
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Operation))==0
    assert client.delete('/api/v1/assistant/connection').status_code==200


def test_missing_reply_and_malformed_job_remain_recoverable(client,provider):
    first=send(client).json();due(first['id'])
    provider['job'].respond(200,json={'job':{'status':'succeeded'}})
    assert client.get('/api/v1/assistant/messages/'+first['id']).status_code==502
    assert client.get('/api/v1/assistant/connection').json()['pending_turn_id']==first['id']
    due(first['id']);provider['job'].respond(200,json={'job':None})
    assert client.get('/api/v1/assistant/messages/'+first['id']).status_code==502


def test_connection_csrf_and_provider_errors_do_not_leak_tokens(client):
    assert client.post('/api/v1/assistant/connection',json={'access_token':TOKEN},headers={'X-CSRF-Token':'wrong'}).status_code==403
    with respx.mock as router:
        router.get(settings().peoplewelcome_issuer+'/oidc/v1/userinfo').respond(401,text=TOKEN)
        response=client.post('/api/v1/assistant/connection',json={'access_token':TOKEN})
        assert response.status_code==424 and TOKEN not in response.text


def test_explicit_rejection_releases_turn_without_retrying_model(client,provider):
    provider['submit'].respond(422,json={'detail':TOKEN})
    response=send(client)
    assert response.status_code==422 and TOKEN not in response.text
    assert client.get('/api/v1/assistant/connection').json()['pending_turn_id'] is None
    with transaction() as db:
        turn=db.scalar(select(AssistantTurn));turn_id=turn.id
        assert turn.status=='failed' and turn.job_id is None
    assert send(client).json()['status']=='failed'
    assert provider['submit'].call_count==1
    assert client.get('/api/v1/assistant/messages/'+turn_id).json()['error']
    assert client.delete('/api/v1/assistant/connection').status_code==200


def test_sensitive_validation_input_is_not_reflected(client):
    response=client.post('/api/v1/assistant/connection',json={'access_token':TOKEN*1000})
    assert response.status_code==422 and TOKEN not in response.text
    response=client.post('/api/v1/assistant/connection',json={'access_token':TOKEN+'\n'})
    assert response.status_code==422 and TOKEN not in response.text


def test_other_customer_cannot_poll_or_resume_turn(client,provider):
    from nebula.assistant import advance
    from fastapi import HTTPException
    turn=send(client).json()
    with transaction() as db:
        other=User(email='unrelated@example.com',password_hash='unused');db.add(other);db.flush();other_id=other.id
    for submit in [False,True]:
        with pytest.raises(HTTPException) as exc:
            advance(other_id,turn['id'],submit=submit)
        assert exc.value.status_code==404
    assert provider['submit'].call_count==1 and provider['job'].call_count==0
