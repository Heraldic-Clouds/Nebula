from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError
from nebula.billing import hourly, journal, settle
from nebula.db import transaction
from nebula.models import Instance, Ledger, Project, Rate, Usage, User, now


def test_hourly_unit_conversion():
    rate = SimpleNamespace(cpu=1000,ram=1000,storage=730000)
    assert hourly(rate,1,1024,1) == Decimal(1000) + Decimal("1073.741824") + Decimal("1073.741824")


def test_ledger_is_balanced_idempotent_and_immutable(customer):
    user_id,_,_=customer
    with transaction() as db:
        user=db.scalar(select(User).where(User.id==user_id).with_for_update())
        journal(db,user,"test-topup",1_000_000,"topup")
        journal(db,user,"test-topup",1_000_000,"topup")
        assert user.balance == 1_000_000
    with pytest.raises(DBAPIError), transaction() as db:
        db.execute(text("UPDATE ledger SET amount=0,counter_amount=0"))
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Ledger)) == 1


def test_final_interval_replay_and_fraction_carry(customer):
    uid,pid,rid=customer
    start=now()-timedelta(hours=1)
    with transaction() as db:
        user=db.get(User,uid)
        instance=Instance(project_id=pid,name="metered",request={},rate_id=rid,vcpus=1,ram_mb=1024,disk_gb=10,last_metered_at=start)
        db.add(instance);db.flush()
        ident=instance.id
        for second in range(1,61):
            settle(db,user,instance,start+timedelta(seconds=second),final=True)
        expected=hourly(db.get(Rate,rid),1,1024,10)/60
        assert user.balance == -int(expected)
        settle(db,user,instance,start+timedelta(seconds=60),final=True)
    with transaction() as db:
        assert db.scalar(select(func.count()).select_from(Usage))==60
        assert db.get(Instance,ident).remainder >= 0


def test_concurrent_credit_serializes(customer):
    user_id,_,_=customer
    def credit(_):
        with transaction() as db:
            user=db.scalar(select(User).where(User.id==user_id).with_for_update())
            journal(db,user,"same-stripe-session",1_000_000,"topup")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(credit,range(8)))
    with transaction() as db:
        assert db.get(User,user_id).balance==1_000_000
        assert db.scalar(select(func.count()).select_from(Ledger))==1
