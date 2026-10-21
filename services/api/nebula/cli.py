import argparse
import getpass
import os
from pathlib import Path
from urllib.parse import urlparse
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from sqlalchemy import select, update
from .config import settings
from .db import transaction
from .models import Operation, Project, Rate, User
from .security import encrypt_credentials


def main():
    p = argparse.ArgumentParser(prog="nebula")
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("init-env", help="Create a private .env with a new encryption key; never print it")
    commands.add_parser("migrate")
    customer = commands.add_parser("create-customer")
    customer.add_argument("--email", required=True)
    customer.add_argument("--spend-limit-usd", type=int, default=100)
    bind = commands.add_parser("bind-project")
    bind.add_argument("--email", required=True)
    bind.add_argument("--project-id")
    bind.add_argument("--auth-url")
    bind.add_argument("--credentials-stdin", action="store_true", help="Read bootstrap credentials JSON from stdin, never argv")
    bind.add_argument("--region", default="RegionOne")
    bind.add_argument("--interface", choices=["public", "internal"], default="internal")
    bind.add_argument("--ca-file")
    bind.add_argument("--catalog", type=Path, required=True, help="JSON with operator-approved images, flavors and tenant networks")
    rates = commands.add_parser("rates")
    rates.add_argument("--cpu-micro-usd", type=int, required=True)
    rates.add_argument("--ram-gb-micro-usd", type=int, required=True)
    rates.add_argument("--storage-gb-month-micro-usd", type=int, required=True)
    retry = commands.add_parser("reconcile-operation")
    retry.add_argument("operation_id")
    args = p.parse_args()
    if args.command == "init-env":
        template = Path(".env.example").read_text()
        template = template.replace("NEBULA_CREDENTIAL_KEY=", "NEBULA_CREDENTIAL_KEY=" + Fernet.generate_key().decode())
        import secrets
        password = secrets.token_urlsafe(24)
        template = template.replace("NEBULA_DB_PASSWORD=", "NEBULA_DB_PASSWORD=" + password)
        template = template.replace("postgresql+psycopg://nebula:REPLACE@postgres:5432/nebula", f"postgresql+psycopg://nebula:{password}@postgres:5432/nebula")
        fd = os.open(".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            file.write(template)
        print("Created .env. Keep it private; configure actual provider credentials locally.")
        return
    if args.command == "migrate":
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config("alembic.ini"), "head")
        print("Database migrated")
        return
    with transaction() as db:
        if args.command == "create-customer":
            from email_validator import validate_email
            email = validate_email(args.email, check_deliverability=False).normalized.lower()
            password = getpass.getpass("New customer password (12+ characters): ")
            if len(password) < 12 or args.spend_limit_usd < 1:
                p.error("Use a password of at least 12 characters and a positive spending limit")
            db.add(User(email=email, password_hash=PasswordHasher().hash(password), spend_limit=args.spend_limit_usd * 1_000_000))
            print("Created pilot customer. No credit or OpenStack access was granted.")
        elif args.command == "bind-project":
            import json
            import sys
            supplied = json.loads(sys.stdin.read(65536)) if args.credentials_stdin else {}
            args.project_id = args.project_id or supplied.get("project_id")
            args.auth_url = args.auth_url or supplied.get("auth_url")
            if not args.project_id or not args.auth_url:
                p.error("Supply --project-id/--auth-url or the bootstrap credentials through stdin")
            user = db.scalar(select(User).where(User.email == args.email.lower()).with_for_update())
            if not user:
                p.error("Create the customer first")
            if db.scalar(select(Project).where(Project.user_id == user.id)):
                p.error("Project already assigned. Rotate/rebind only through a reviewed migration.")
            endpoint = urlparse(args.auth_url)
            if endpoint.scheme not in {"http", "https"} or not endpoint.netloc or endpoint.username:
                p.error("Supply a valid operator-controlled Keystone endpoint without embedded credentials")
            credential_id = supplied.get("credential_id") or os.environ.get("OS_APPLICATION_CREDENTIAL_ID")
            secret = supplied.get("credential_secret") or os.environ.get("OS_APPLICATION_CREDENTIAL_SECRET")
            if not credential_id or not secret:
                p.error("Export the customer's scoped OS_APPLICATION_CREDENTIAL_ID and OS_APPLICATION_CREDENTIAL_SECRET")
            catalog = json.loads(args.catalog.read_text())
            if any(not isinstance(catalog.get(k), list) or not catalog[k] for k in ["images", "flavors", "networks"]):
                p.error("Catalog must contain nonempty image/flavor/network ID lists")
            project = Project(user_id=user.id, provider_id=args.project_id, auth_url=args.auth_url, region=args.region,
                interface=args.interface, ca_file=args.ca_file, credential=encrypt_credentials(credential_id, secret), catalog=catalog)
            # Verify actual authentication and tenant ownership before storing the mapping.
            from .cloud import Cloud
            cloud = Cloud(project)
            try:
                cloud.catalog()
            finally:
                cloud.close()
            db.add(project)
            print("Verified and assigned the customer's scoped OpenStack project")
        elif args.command == "rates":
            amounts = [args.cpu_micro_usd, args.ram_gb_micro_usd, args.storage_gb_month_micro_usd]
            if any(v < 0 for v in amounts) or not any(amounts):
                p.error("Rates must be nonnegative with a positive billable rate")
            db.execute(update(Rate).values(active=False))
            db.add(Rate(cpu=amounts[0], ram=amounts[1], storage=amounts[2]))
            print("Activated rate card. Existing instances retain their immutable launch rate version.")
        elif args.command == "reconcile-operation":
            op = db.get(Operation, args.operation_id)
            if not op or op.status != "needs_attention":
                p.error("Select an operation needing operator reconciliation")
            op.status = "reconciling"
            op.error = None
            print("Queued reconciliation. This will search for the existing VM; it never blindly repeats creation.")


if __name__ == "__main__":
    main()
