import math
import secrets
from decimal import Decimal
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Annotated
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from . import payments
from .billing import active_rate, hourly
from .cloud import Cloud
from .config import settings
from .db import transaction
from .models import Audit, Instance, Ledger, LoginAttempt, LoginSession, Operation, Project, Rate, Topup, Usage, User, now
from .security import digest, fingerprint, token

hasher = PasswordHasher()
dummy_hash = hasher.hash("a-never-valid-nebula-password")


def database():
    with transaction() as db:
        yield db


DB = Annotated[Session, Depends(database)]


def current_user(request: Request, db: DB):
    auth = db.get(LoginSession, digest(request.cookies.get("nebula_session", "")))
    if not auth or auth.expires_at <= now():
        raise HTTPException(401, "Sign in to Nebula")
    user = db.get(User, auth.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Account disabled")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != settings().public_url.rstrip("/"):
            raise HTTPException(403, "Invalid request origin")
        if not secrets.compare_digest(auth.csrf_hash, digest(request.headers.get("x-csrf-token", ""))):
            raise HTTPException(403, "Invalid CSRF token")
    return user


Actor = Annotated[User, Depends(current_user)]


def project_for(db, user):
    project = db.scalar(select(Project).where(Project.user_id == user.id))
    if not project:
        raise HTTPException(503, "Your cloud project is awaiting operator setup. Contact your Nebula operator.")
    return project


def lock_user(db, user):
    return db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))


def record(db, user, action, **detail):
    db.add(Audit(user_id=user.id, action=action, detail=detail))


def operation_view(op):
    return {"id": op.id, "instance_id": op.instance_id, "action": op.action, "status": op.status, "error": op.error}


def instance_view(i):
    return {"id": i.id, "provider_id": i.provider_id, "name": i.name, "status": i.state,
        "vcpus": i.vcpus, "ram_mb": i.ram_mb, "disk_gb": i.disk_gb, "addresses": i.addresses,
        "observed_at": i.observed_at, "created_at": i.created_at, "deleted_at": i.deleted_at}


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class Launch(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,62}$")
    image_id: str = Field(min_length=1, max_length=128)
    flavor_id: str = Field(min_length=1, max_length=128)
    network_id: str = Field(min_length=1, max_length=128)
    key_name: str = Field(min_length=1, max_length=128)
    confirmed: bool = False
    rate_id: str = Field(min_length=1, max_length=36)


class SSHKey(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,63}$")
    public_key: str = Field(min_length=20, max_length=8192)


class TopupRequest(BaseModel):
    dollars: int = Field(ge=1, le=1000, strict=True)


app = FastAPI(title="Nebula", version="0.1.0")


@app.exception_handler(Exception)
async def service_error(request, exc):
    import logging
    # Provider exceptions can include credentials/URLs. Log only the class.
    logging.getLogger("nebula").error("Request failed: %s", type(exc).__name__)
    return JSONResponse({"detail": "Service unavailable; operator diagnostics required", "error_type": type(exc).__name__}, status_code=503)


@app.middleware("http")
async def security_headers(request, call_next):
    if int(request.headers.get("content-length", "0") or "0") > 65536:
        return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/v1/health/live")
def live():
    return {"status": "up", "provider": "openstack", "payment_mode": "test"}


@app.get("/api/v1/health/ready")
def ready(db: DB):
    db.execute(text("SELECT 1"))
    return {"status": "ready", "cloud_validated": False, "provisioning_enabled": settings().provisioning_enabled}


@app.post("/api/v1/auth/login")
def login(body: Login, request: Request, response: Response):
    if request.headers.get("origin") and request.headers["origin"].rstrip("/") != settings().public_url.rstrip("/"):
        raise HTTPException(403, "Invalid request origin")
    email = str(body.email).lower()
    key = digest((request.client.host if request.client else "unknown") + ":" + email)
    with transaction() as db:
        db.execute(insert(LoginAttempt).values(key=key, count=0, window_at=now()).on_conflict_do_nothing())
        attempt = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key).with_for_update())
        if now() - attempt.window_at > timedelta(minutes=15):
            attempt.count, attempt.window_at = 0, now()
        limited = attempt.count >= 10
        attempt.count += 1
        user = db.scalar(select(User).where(User.email == email))
        valid = False
        try:
            valid = hasher.verify(user.password_hash if user else dummy_hash, body.password)
        except VerificationError:
            pass
        if user and user.active and valid and not limited:
            session_token, csrf = token(), token()
            db.add(LoginSession(token_hash=digest(session_token), csrf_hash=digest(csrf), user_id=user.id,
                expires_at=now() + timedelta(hours=settings().session_hours)))
            record(db, user, "login")
            attempt.count = 0
    if limited:
        raise HTTPException(429, "Too many login attempts; try again in 15 minutes")
    if not user or not user.active or not valid:
        raise HTTPException(401, "Invalid email or password")
    response.set_cookie("nebula_session", session_token, httponly=True, secure=settings().cookie_secure,
                        samesite="strict", max_age=settings().session_hours * 3600)
    response.set_cookie("nebula_csrf", csrf, httponly=False, secure=settings().cookie_secure, samesite="strict",
                        max_age=settings().session_hours * 3600)
    return {"email": user.email}


@app.post("/api/v1/auth/logout")
def logout(request: Request, response: Response, user: Actor, db: DB):
    db.delete(db.get(LoginSession, digest(request.cookies["nebula_session"])))
    response.delete_cookie("nebula_session")
    response.delete_cookie("nebula_csrf")
    return {"ok": True}


@app.get("/api/v1/me")
def me(user: Actor, db: DB):
    project = db.scalar(select(Project).where(Project.user_id == user.id))
    return {"id": user.id, "email": user.email, "project_id": project.id if project else None,
            "provisioning_enabled": settings().provisioning_enabled}


@app.get("/api/v1/catalog")
def catalog(user: Actor, db: DB):
    cloud = Cloud(project_for(db, user))
    try:
        value = cloud.catalog()
        rate = active_rate(db)
        for f in value["flavors"]:
            f["hourly_micro_usd"] = math.ceil(hourly(rate, f["vcpus"], f["ram_mb"], f["disk_gb"]))
        return {**value, "rate_id": rate.id, "currency": "USD", "storage_month_hours": 730}
    finally:
        cloud.close()


@app.post("/api/v1/ssh-keys")
def ssh_key(body: SSHKey, user: Actor, db: DB):
    cloud = Cloud(project_for(db, user))
    try:
        value = cloud.keys_add(body.name, body.public_key.strip())
        record(db, user, "ssh_key_add", name=body.name)
        return value
    finally:
        cloud.close()


@app.get("/api/v1/instances")
def instances(user: Actor, db: DB):
    project = project_for(db, user)
    rows = db.scalars(select(Instance).where(Instance.project_id == project.id).order_by(Instance.created_at.desc()).limit(200))
    return {"instances": [instance_view(i) for i in rows], "last_collected_at": project.last_collected_at,
            "collection_error": project.collection_error}


@app.post("/api/v1/instances", status_code=202)
def create_instance(body: Launch, user: Actor, db: DB, idempotency_key: Annotated[str, Header(min_length=8, max_length=100)]):
    user = lock_user(db, user)
    project = project_for(db, user)
    request = body.model_dump(exclude={"confirmed", "rate_id"})
    request_hash = fingerprint({**request, "rate_id": body.rate_id})
    existing = db.scalar(select(Operation).where(Operation.project_id == project.id, Operation.action == "create", Operation.key == idempotency_key))
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key was used with different parameters")
        return operation_view(existing)
    if not settings().provisioning_enabled:
        raise HTTPException(503, "Provisioning disabled until live infrastructure is approved and verified")
    if not body.confirmed:
        raise HTTPException(422, "Explicit confirmation of the billable VM creation is required")
    if not project.last_collected_at or (now() - project.last_collected_at).total_seconds() > settings().metering_stale_seconds or project.collection_error:
        raise HTTPException(503, "Metering is stale or incomplete; run the worker and reconcile the project")
    rate = active_rate(db)
    if body.rate_id != rate.id:
        raise HTTPException(409, "Rates changed; refresh the estimate and confirm again")
    cloud = Cloud(project)
    try:
        flavor = cloud.validate(request)
    finally:
        cloud.close()
    active = list(db.scalars(select(Instance).where(Instance.project_id == project.id, Instance.deleted_at.is_(None), Instance.state != "FAILED")))
    if len(active) >= settings().max_instances:
        raise HTTPException(409, "Instance quota reached")
    reserve = math.ceil(hourly(rate, flavor["vcpus"], flavor["ram_mb"], flavor["disk_gb"]))
    if reserve <= 0:
        raise HTTPException(503, "Billable rates must be configured before provisioning")
    pending = 0
    for i in active:
        if i.last_metered_at:
            r = db.get(Rate, i.rate_id)
            pending += math.ceil(hourly(r, i.vcpus, i.ram_mb, i.disk_gb) * Decimal(str(max(0, (now()-i.last_metered_at).total_seconds()))) / 3600)
    spent = -(db.scalar(select(func.coalesce(func.sum(Ledger.amount), 0)).where(Ledger.user_id == user.id, Ledger.kind == "usage")) or 0)
    if user.balance - user.reserved - pending < reserve:
        raise HTTPException(409, "Insufficient prepaid balance for a one-hour reservation")
    if spent + pending + user.reserved + reserve > user.spend_limit:
        raise HTTPException(409, "Pilot lifetime spending limit reached")
    instance = Instance(project_id=project.id, name=body.name, request=request, rate_id=rate.id,
        vcpus=flavor["vcpus"], ram_mb=flavor["ram_mb"], disk_gb=flavor["disk_gb"], reservation=reserve)
    db.add(instance)
    user.reserved += reserve
    db.flush()
    op = Operation(project_id=project.id, instance_id=instance.id, action="create", key=idempotency_key, request_hash=request_hash)
    db.add(op)
    db.flush()
    record(db, user, "create_confirmed", operation_id=op.id, instance_id=instance.id)
    return operation_view(op)


@app.delete("/api/v1/instances/{instance_id}", status_code=202)
def delete_instance(instance_id: str, user: Actor, db: DB,
                    idempotency_key: Annotated[str, Header(min_length=8, max_length=100)], confirmed: bool = False):
    user = lock_user(db, user)
    project = project_for(db, user)
    instance = db.scalar(select(Instance).where(Instance.id == instance_id, Instance.project_id == project.id))
    if not instance:
        raise HTTPException(404, "Instance not found")
    if not confirmed:
        raise HTTPException(422, "Explicit confirmation of VM data loss is required")
    existing = db.scalar(select(Operation).where(Operation.project_id == project.id, Operation.action == "delete", Operation.key == idempotency_key))
    if existing:
        if existing.instance_id != instance_id:
            raise HTTPException(409, "Idempotency key was used for another instance")
        return operation_view(existing)
    if instance.deleted_at:
        return {"instance_id": instance.id, "status": "succeeded", "action": "delete"}
    if not instance.provider_id:
        raise HTTPException(409, "Creation must be reconciled before deleting this instance")
    op = Operation(project_id=project.id, instance_id=instance.id, action="delete", key=idempotency_key, request_hash=fingerprint(instance.id))
    db.add(op)
    db.flush()
    record(db, user, "delete_confirmed", operation_id=op.id, instance_id=instance.id)
    return operation_view(op)


@app.get("/api/v1/operations/{operation_id}")
def get_operation(operation_id: str, user: Actor, db: DB):
    project = project_for(db, user)
    op = db.scalar(select(Operation).where(Operation.id == operation_id, Operation.project_id == project.id))
    if not op:
        raise HTTPException(404, "Operation not found")
    return operation_view(op)


@app.get("/api/v1/billing")
def billing(user: Actor, db: DB):
    entries = db.scalars(select(Ledger).where(Ledger.user_id == user.id).order_by(Ledger.created_at.desc()).limit(100))
    return {"balance_micro_usd": user.balance, "reserved_micro_usd": user.reserved, "spend_limit_micro_usd": user.spend_limit,
        "payment_mode": "test", "ledger": [{"id": e.id, "kind": e.kind, "amount_micro_usd": e.amount, "created_at": e.created_at, "detail": e.detail} for e in entries]}


@app.get("/api/v1/usage")
def usage(user: Actor, db: DB):
    project = project_for(db, user)
    rows = db.execute(select(Usage, Instance.name).join(Instance).where(Instance.project_id == project.id).order_by(Usage.end.desc()).limit(200))
    return {"last_collected_at": project.last_collected_at, "collection_error": project.collection_error,
        "coverage": "Nebula-managed root-disk instances; no unattached volume/public-IP collection yet",
        "intervals": [{"id": u.id, "instance": name, "start": u.start, "end": u.end, "cost_micro_usd": u.cost, "quantities": u.quantities} for u, name in rows]}


@app.post("/api/v1/billing/checkout-sessions")
def topup(body: TopupRequest, user: Actor, idempotency_key: Annotated[str, Header(min_length=8, max_length=100)]):
    # Persist intent before the remote call, so an ambiguous timeout retains its stable identity.
    with transaction() as db:
        user = lock_user(db, user)
        existing = db.scalar(select(Topup).where(Topup.user_id == user.id, Topup.key == idempotency_key))
        if not existing:
            db.add(Topup(user_id=user.id, key=idempotency_key, amount_cents=body.dollars * 100))
    with transaction() as db:
        user = lock_user(db, user)
        return payments.checkout(db, user, body.dollars * 100, idempotency_key)


@app.post("/api/v1/webhooks/stripe")
async def webhook(request: Request):
    payload = await request.body()
    if len(payload) > 65536:
        raise HTTPException(413, "Webhook too large")
    event = payments.verify_event(payload, request.headers.get("stripe-signature"))
    def process():
        with transaction() as db:
            payments.fulfill(db, event)
    await run_in_threadpool(process)
    return {"received": True}


class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@app.post("/api/v1/assistant/messages")
def assistant(body: Chat, user: Actor, db: DB):
    from .assistant import answer
    project = project_for(db, user)
    record(db, user, "assistant_read", project_id=project.id)
    return answer(db, user, project, body.message)


dist = Path(settings().dashboard_dist)
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
