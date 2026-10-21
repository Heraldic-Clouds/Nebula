from decimal import Decimal, ROUND_DOWN
from sqlalchemy import select
from fastapi import HTTPException
from .models import Ledger, Rate, Usage, now

MICRO = 1_000_000


def active_rate(db):
    rate = db.scalar(select(Rate).where(Rate.active.is_(True)).order_by(Rate.created_at.desc()))
    if not rate:
        raise HTTPException(503, "Instance pricing is not configured. Contact your Nebula operator.")
    return rate


def hourly(rate, vcpus, ram_mb, disk_gb):
    # Nova RAM is MiB and disk is GiB; public units are decimal GB.
    ram_gb = Decimal(ram_mb) * 1048576 / 1_000_000_000
    storage_gb = Decimal(disk_gb) * 1073741824 / 1_000_000_000
    return Decimal(rate.cpu) * vcpus + Decimal(rate.ram) * ram_gb + Decimal(rate.storage) * storage_gb / 730


def journal(db, user, source, amount, kind, detail=None):
    existing = db.scalar(select(Ledger).where(Ledger.source == source))
    if existing:
        return existing
    row = Ledger(user_id=user.id, source=source, kind=kind, amount=amount, counter_amount=-amount, detail=detail or {})
    db.add(row)
    user.balance += amount
    db.flush()
    return row


def settle(db, user, instance, end, *, final=False):
    start = instance.last_metered_at
    if not start or end <= start:
        return
    duration = Decimal(str((end - start).total_seconds()))
    if duration < 3600 and not final:
        return
    rate = db.get(Rate, instance.rate_id)
    raw = hourly(rate, instance.vcpus, instance.ram_mb, instance.disk_gb) * duration / 3600 + Decimal(instance.remainder)
    cost = int(raw.to_integral_value(rounding=ROUND_DOWN))
    instance.remainder = raw - cost
    instance.last_metered_at = end
    quantities = {
        "seconds": str(duration), "vcpus": instance.vcpus, "ram_mib": instance.ram_mb,
        "disk_gib": instance.disk_gb, "coverage": "observed_managed_instance", "public_ip_hours": "0",
    }
    db.add(Usage(instance_id=instance.id, start=start, end=end, quantities=quantities, cost=cost, rate_id=rate.id))
    journal(db, user, f"usage:{instance.id}:{end.isoformat()}", -cost, "usage", quantities)


def release(user, instance):
    user.reserved -= instance.reservation
    instance.reservation = 0
