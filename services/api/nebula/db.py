from contextlib import contextmanager
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings


@lru_cache
def engine():
    return create_engine(settings().database_url, pool_pre_ping=True)


@contextmanager
def transaction():
    with sessionmaker(bind=engine(), expire_on_commit=False)() as session:
        with session.begin():
            yield session
