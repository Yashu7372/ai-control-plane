import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

def database_url() -> str:
    default = Path.home() / ".ai-control-plane" / "control-plane.sqlite"
    default.parent.mkdir(parents=True, exist_ok=True)
    return os.getenv("AI_CONTROL_PLANE_DB", f"sqlite:///{default}")

engine = create_engine(database_url(), future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db() -> None:
    from . import models  # noqa: F401
    Base.metadata.create_all(engine)
