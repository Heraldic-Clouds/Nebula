from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from nebula.cloud import Cloud
from nebula.db import transaction
from nebula.models import Project


def test_openstack_scope_must_match_bound_project(customer,monkeypatch):
    _,pid,_=customer
    calls=[]
    def connection(**kw):
        calls.append(kw)
        return SimpleNamespace(session=SimpleNamespace(get_project_id=lambda:'another-tenant'))
    monkeypatch.setattr('nebula.cloud.Connection',connection)
    with transaction() as db,pytest.raises(HTTPException) as e:
        Cloud(db.get(Project,pid))
    assert e.value.status_code==503
    assert calls[0]['auth_type']=='v3applicationcredential'
    assert calls[0]['verify'] is True
    assert calls[0]['load_envvars'] is False
