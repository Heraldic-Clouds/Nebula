import hashlib
import json
import secrets
from cryptography.fernet import Fernet
from fastapi import HTTPException
from .config import settings


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")))


def cipher():
    key = settings().credential_key
    if not key:
        raise HTTPException(503, "OpenStack credential storage is awaiting operator setup.")
    return Fernet(key.encode())


def encrypt_credentials(credential_id, secret):
    return cipher().encrypt(json.dumps({"id": credential_id, "secret": secret}).encode()).decode()


def decrypt_credentials(value):
    return json.loads(cipher().decrypt(value.encode()))


def token():
    return secrets.token_urlsafe(32)
