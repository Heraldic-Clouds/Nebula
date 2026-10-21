import hashlib
import hmac
import json
import time
import stripe
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from nebula import payments
from nebula.config import settings
from nebula.db import transaction
from nebula.models import Topup,User,Ledger


def test_real_stripe_signature_verification(monkeypatch):
    monkeypatch.setenv('NEBULA_STRIPE_WEBHOOK_SECRET','unit-test-signing-key')
    settings.cache_clear()
    raw=json.dumps({'id':'evt_signed','type':'test.event','livemode':False,'data':{'object':{}}}).encode()
    stamp=str(int(time.time()))
    sig=hmac.new(b'unit-test-signing-key',stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    assert payments.verify_event(raw,f't={stamp},v1={sig}')['id']=='evt_signed'
    with pytest.raises(HTTPException) as err:
        payments.verify_event(raw+b' ',f't={stamp},v1={sig}')
    assert err.value.status_code==400
    settings.cache_clear()


def test_live_keys_are_rejected(monkeypatch):
    monkeypatch.setenv('NEBULA_STRIPE_API_KEY','sk_live_not_a_real_key')
    settings.cache_clear()
    with pytest.raises(HTTPException) as err:payments.client()
    assert err.value.status_code==503
    settings.cache_clear()


def test_paid_session_credited_once_across_event_types(customer,monkeypatch):
    uid,_,_=customer
    with transaction() as db:
        topup=Topup(user_id=uid,key='topup-key',amount_cents=1000,session_id='cs_test_fixture')
        db.add(topup);db.flush();topup_id=topup.id
    session=SimpleNamespace(id='cs_test_fixture',livemode=False,currency='usd',amount_total=1000,
        client_reference_id=topup_id,metadata={'nebula_topup':topup_id},payment_status='unpaid')
    fake=SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(retrieve=lambda ident:stripe.checkout.Session.construct_from(vars(session),'test')))))
    monkeypatch.setattr(payments,'client',lambda:fake)
    def event(ident,kind):return {'id':ident,'type':kind,'data':{'object':{'id':'cs_test_fixture'}}}
    with transaction() as db:payments.fulfill(db,event('evt_pending','checkout.session.completed'))
    with transaction() as db:assert db.get(User,uid).balance==0
    session.payment_status='paid'
    for ident,kind in [('evt_success','checkout.session.async_payment_succeeded'),('evt_success','checkout.session.async_payment_succeeded'),('evt_other','checkout.session.completed')]:
        with transaction() as db:payments.fulfill(db,event(ident,kind))
    with transaction() as db:
        assert db.get(User,uid).balance==10_000_000
        assert db.scalar(select(func.count()).select_from(Ledger))==1


def test_wrong_currency_never_grants_credit(customer,monkeypatch):
    uid,_,_=customer
    with transaction() as db:
        t=Topup(user_id=uid,key='bad-currency',amount_cents=1000,session_id='cs_bad');db.add(t);db.flush();tid=t.id
    obj=SimpleNamespace(id='cs_bad',livemode=False,currency='eur',amount_total=1000,client_reference_id=tid,metadata={'nebula_topup':tid},payment_status='paid')
    monkeypatch.setattr(payments,'client',lambda:SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=SimpleNamespace(retrieve=lambda ident:stripe.checkout.Session.construct_from(vars(obj),'test'))))))
    with pytest.raises(HTTPException), transaction() as db:
        payments.fulfill(db,{'id':'evt_bad','type':'checkout.session.completed','data':{'object':{'id':'cs_bad'}}})
    with transaction() as db:assert db.get(User,uid).balance==0
