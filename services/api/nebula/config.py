from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NEBULA_", extra="ignore")
    database_url: str = "postgresql+psycopg://nebula:nebula@localhost:5432/nebula"
    credential_key: str = ""
    public_url: str = "http://localhost:8080"
    cookie_secure: bool = True
    session_hours: int = 12
    provisioning_enabled: bool = False
    max_instances: int = 5
    metering_stale_seconds: int = 900
    worker_interval_seconds: int = 30
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_api_version: str = "2026-09-30.endive"
    stripe_integration_id: str = "nebula_pilot_abcdefgh"
    peoplewelcome_api_url: str = "https://peopl.ewelco.me"
    peoplewelcome_issuer: str = "https://pplwlcm1-ysqkpd.us1.zitadel.cloud"
    dashboard_dist: str = "apps/dashboard/dist"


@lru_cache
def settings():
    return Settings()
