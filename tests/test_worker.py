from datetime import timedelta
from types import SimpleNamespace
from sqlalchemy import select
from nebula import worker
from nebula.db import transaction
from nebula.models import Instance,Operation,Project,User,Usage,now
from nebula.billing import journal
from test_api import TestOnlyCloud,payload


def test_durable_create_observe_usage_and_delete(client,customer,monkeypatch):
    uid,pid,rid=customer
    monkeypatch.setattr('nebula.api.Cloud',TestOnlyCloud)
    with transaction() as db:journal(db,db.get(User,uid),'credit',2_000_000,'topup')
    created=client.post('/api/v1/instances',json=payload(rid),headers={'Idempotency-Key':'worker-happy-path'})
    assert created.status_code==202,created.text
    opid=created.json()['id']
    resources={}
    class TestOnlyWorkerCloud:
        def __init__(self,project):
            self.project=project
            self.conn=SimpleNamespace(compute=SimpleNamespace(servers=lambda **kw:list(resources.values())))
        def close(self):pass
        def owned(self,s):return s
        def find_operation(self,ident):return [s for s in resources.values() if s.metadata['nebula_operation']==ident]
        def create(self,ident,req):
            resources['nova-test-id']=SimpleNamespace(id='nova-test-id',status='ACTIVE',addresses={},flavor={'vcpus':1,'ram':1024,'disk':10},launched_at=now()-timedelta(hours=1,minutes=1),metadata={'nebula_operation':ident})
            return resources['nova-test-id']
        def get(self,ident):return resources.get(ident)
        def delete(self,ident):resources.pop(ident,None)
    monkeypatch.setattr(worker,'Cloud',TestOnlyWorkerCloud)
    worker.run_operation()
    worker.collect_project(pid)
    with transaction() as db:
        assert db.get(Operation,opid).status=='succeeded'
        instance=db.scalar(select(Instance));ident=instance.id
        assert instance.provider_id=='nova-test-id'
        assert db.scalar(select(Usage)).cost>0
        assert db.get(User,uid).reserved==0
    deleted=client.delete(f'/api/v1/instances/{ident}?confirmed=true',headers={'Idempotency-Key':'worker-delete-path'})
    assert deleted.status_code==202
    worker.run_operation()
    with transaction() as db:db.get(Operation,deleted.json()['id']).available_at=now()-timedelta(seconds=1)
    worker.run_operation()
    with transaction() as db:
        assert db.get(Instance,ident).deleted_at is not None
        assert db.get(Operation,deleted.json()['id']).status=='succeeded'
    assert client.get('/api/v1/instances').json()['instances'][0]['status']=='DELETED'


def test_ambiguous_create_is_not_repeated(client,customer,monkeypatch):
    uid,pid,rid=customer
    monkeypatch.setattr('nebula.api.Cloud',TestOnlyCloud)
    with transaction() as db:journal(db,db.get(User,uid),'credit',2_000_000,'topup')
    response=client.post('/api/v1/instances',json=payload(rid),headers={'Idempotency-Key':'ambiguous-create'})
    calls=[]
    class Ambiguous:
        def __init__(self,project):pass
        def close(self):pass
        def find_operation(self,ident):return []
        def create(self,*args):calls.append(1);raise TimeoutError('test timeout after dispatch')
    monkeypatch.setattr(worker,'Cloud',Ambiguous)
    worker.run_operation()
    with transaction() as db:
        op=db.get(Operation,response.json()['id']);assert op.status=='needs_attention';op.status='reconciling'
    worker.run_operation()
    assert len(calls)==1


def test_worker_never_dispatches_queued_create_when_disabled(client,customer,monkeypatch):
    uid,pid,rid=customer
    monkeypatch.setattr('nebula.api.Cloud',TestOnlyCloud)
    with transaction() as db:journal(db,db.get(User,uid),'credit',2_000_000,'topup')
    response=client.post('/api/v1/instances',json=payload(rid),headers={'Idempotency-Key':'disabled-worker'})
    assert response.status_code==202
    from nebula.config import settings
    monkeypatch.setenv('NEBULA_PROVISIONING_ENABLED','false');settings.cache_clear()
    class NoDispatch:
        def __init__(self,project):pass
        def close(self):pass
        def find_operation(self,ident):return []
        def create(self,*args):raise AssertionError('Must not dispatch while disabled')
    monkeypatch.setattr(worker,'Cloud',NoDispatch)
    worker.run_operation()
    with transaction() as db:
        op=db.get(Operation,response.json()['id'])
        assert op.status=='queued' and op.error=='provisioning_disabled'
