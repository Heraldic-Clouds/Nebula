import json
import httpx
import pytest
import respx
from fastapi import HTTPException
from nebula.assistant import answer
from nebula.config import settings
from nebula.db import transaction
from nebula.models import Project,User


def configure(monkeypatch):
    monkeypatch.setenv('NEBULA_PEOPLEWELCOME_API_URL','https://peoplewelcome.example.invalid/v1/chat/completions')
    monkeypatch.setenv('NEBULA_PEOPLEWELCOME_API_KEY','test-only-fixture')
    monkeypatch.setenv('NEBULA_PEOPLEWELCOME_MODEL','gpt-6-luna')
    monkeypatch.setenv('NEBULA_PEOPLEWELCOME_PROTOCOL','openai-chat-completions')
    settings.cache_clear()


def test_peoplewelcome_read_only_tool_and_model(customer,monkeypatch):
    uid,pid,_=customer;configure(monkeypatch)
    with respx.mock as router:
        route=router.post(settings().peoplewelcome_api_url)
        route.side_effect=[httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'tool1','type':'function','function':{'name':'inspect_project','arguments':'{}'}}]}}]}),httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'No provisioned instances were observed.'}}]})]
        with transaction() as db:
            result=answer(db,db.get(User,uid),db.get(Project,pid),'Show my instances')
        assert result['provider']=='PeopleWelcome'
        sent=json.loads(route.calls[1].request.content)
        assert sent['model']=='gpt-6-luna'
        assert 'secret' not in sent['messages'][-1]['content']
        assert route.call_count==2


def test_assistant_cannot_execute_mutation(customer,monkeypatch):
    uid,pid,_=customer;configure(monkeypatch)
    with respx.mock as router:
        router.post(settings().peoplewelcome_api_url).respond(200,json={'choices':[{'message':{'role':'assistant','tool_calls':[{'id':'evil','function':{'name':'delete_instance','arguments':'{}'}}]}}]})
        with pytest.raises(HTTPException) as e, transaction() as db:
            answer(db,db.get(User,uid),db.get(Project,pid),'Delete everything')
        assert e.value.status_code==403
