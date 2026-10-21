import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved: Mapped[int] = mapped_column(BigInteger, default=0)
    spend_limit: Mapped[int] = mapped_column(BigInteger, default=100_000_000)
    __table_args__ = (CheckConstraint("reserved >= 0", name="positive_reservation"),)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    provider_id: Mapped[str] = mapped_column(String(128), unique=True)
    auth_url: Mapped[str] = mapped_column(Text)
    region: Mapped[str] = mapped_column(String(128), default="RegionOne")
    interface: Mapped[str] = mapped_column(String(32), default="internal")
    credential: Mapped[str] = mapped_column(Text)
    catalog: Mapped[dict] = mapped_column(JSON, default=dict)
    ca_file: Mapped[str | None] = mapped_column(Text)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collection_error: Mapped[str | None] = mapped_column(String(64))


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    window_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Rate(Base):
    __tablename__ = "rates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    cpu: Mapped[int] = mapped_column(BigInteger)
    ram: Mapped[int] = mapped_column(BigInteger)
    storage: Mapped[int] = mapped_column(BigInteger)
    public_ip: Mapped[int] = mapped_column(BigInteger, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("cpu >= 0 AND ram >= 0 AND storage >= 0 AND public_ip >= 0", name="nonnegative_rates"),)


class Instance(Base):
    __tablename__ = "instances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    provider_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(63))
    request: Mapped[dict] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(32), default="QUEUED")
    vcpus: Mapped[int] = mapped_column(Integer)
    ram_mb: Mapped[int] = mapped_column(Integer)
    disk_gb: Mapped[int] = mapped_column(Integer)
    rate_id: Mapped[str] = mapped_column(ForeignKey("rates.id"))
    reservation: Mapped[int] = mapped_column(BigInteger, default=0)
    remainder: Mapped[object] = mapped_column(Numeric(30, 18), default=0)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_metered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    addresses: Mapped[dict] = mapped_column(JSON, default=dict)


class Operation(Base):
    __tablename__ = "operations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("instances.id"))
    action: Mapped[str] = mapped_column(String(16))
    key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    error: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("project_id", "action", "key", name="operation_idempotency"),)


class Ledger(Base):
    __tablename__ = "ledger"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(255), unique=True)
    kind: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(BigInteger)
    counter_amount: Mapped[int] = mapped_column(BigInteger)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("amount + counter_amount = 0", name="balanced_journal"),)


class Usage(Base):
    __tablename__ = "usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("instances.id"), index=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quantities: Mapped[dict] = mapped_column(JSON)
    cost: Mapped[int] = mapped_column(BigInteger)
    rate_id: Mapped[str] = mapped_column(ForeignKey("rates.id"))
    __table_args__ = (UniqueConstraint("instance_id", "end", name="usage_interval_once"), CheckConstraint('"end" > start', name="usage_positive_interval"))


class Topup(Base):
    __tablename__ = "topups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(100))
    amount_cents: Mapped[int] = mapped_column(Integer)
    session_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    checkout_url: Mapped[str | None] = mapped_column(Text)
    fulfilled: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("user_id", "key", name="topup_idempotency"),)


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(128))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
