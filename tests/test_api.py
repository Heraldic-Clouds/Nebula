from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from nebula.api import app
from nebula.billing import journal
from nebula.db import transaction
from nebula.models import User,Instance,Operation,Project,now


class TestOnlyCloud:
    """Explicit unit/integration-test double. Never installed in runtime dependencies."""
    __test__ = False
    def __init__(self,project):self.project=project
    def close(self):pass
    def validate(self,request):return {"vcpus":1,"ram_mb":1024,"disk_gb":10}


def payload(rate):
    return {"name":"ubuntu-test","flavor_id":"small","image_id":"ubuntu","network_id":"private","key_name":"customer-key","rate_id":rate,"confirmed":True}


def test_session_csrf_and_real_unconfigured_cloud(client):
    response=client.post('/api/v1/ssh-keys',json={"name":"key","public_key":"ssh-ed25519 test-public-key"},headers={"X-CSRF-Token":"forged"})
    assert response.status_code==403
    assert client.get('/api/v1/catalog').status_code==503
    assert client.post('/api/v1/assistant/messages',json={"message":"Show my usage"},headers={"Idempotency-Key":"unconfigured-support"}).status_code==503
    assert client.post('/api/v1/auth/logout').status_code==200
    assert client.get('/api/v1/me').status_code==401


def test_create_requires_credit_confirmation_freshness_and_idempotency(client,customer,monkeypatch):
    uid,pid,rid=customer
    monkeypatch.setattr('nebula.api.Cloud',TestOnlyCloud)
    data=payload(rid);headers={"Idempotency-Key":"create-test-key"}
    assert client.post('/api/v1/instances',json=data,headers=headers).status_code==409
    with transaction() as db:
        journal(db,db.get(User,uid),'credit',1_000_000,'topup')
    assert client.post('/api/v1/instances',json={**data,"confirmed":False},headers=headers).status_code==422
    first=client.post('/api/v1/instances',json=data,headers=headers)
    assert first.status_code==202,first.text
    again=client.post('/api/v1/instances',json=data,headers=headers)
    assert again.json()['id']==first.json()['id']
    assert client.post('/api/v1/instances',json={**data,"name":"changed"},headers=headers).status_code==409
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Instance))==1
        db.get(Project,pid).last_collected_at=now()-timedelta(hours=2)
    assert client.post('/api/v1/instances',json=data,headers={"Idempotency-Key":"another-request-key"}).status_code==503


def test_delete_cannot_access_other_tenant(client,customer):
    uid,pid,rid=customer
    with transaction() as db:
        other=User(email='other@example.com',password_hash='unused');db.add(other);db.flush()
        project=Project(user_id=other.id,provider_id='other-tenant',auth_url='https://invalid',credential='encrypted');db.add(project);db.flush()
        vm=Instance(project_id=project.id,name='private',request={},rate_id=rid,vcpus=1,ram_mb=1,disk_gb=1,provider_id='private-id');db.add(vm);db.flush();ident=vm.id
    assert client.delete(f'/api/v1/instances/{ident}?confirmed=true',headers={"Idempotency-Key":"delete-test-key"}).status_code==404


def test_concurrent_admission_cannot_overspend(client,customer,monkeypatch):
    uid,pid,rid=customer
    monkeypatch.setattr('nebula.api.Cloud',TestOnlyCloud)
    with transaction() as db:
        journal(db,db.get(User,uid),'small-credit',13000,'topup')
    cookies=dict(client.cookies)
    def launch(i):
        with TestClient(app,raise_server_exceptions=False) as c:
            c.cookies.update(cookies)
            return c.post('/api/v1/instances',json=payload(rid),headers={'Idempotency-Key':f'concurrent-{i}','X-CSRF-Token':cookies['nebula_csrf']}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=sorted(pool.map(launch,range(2)))
    assert statuses==[202,409]
