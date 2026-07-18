import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now():
    return datetime.now(timezone.utc)

class RunStatus(str, enum.Enum):
    RUNNING="RUNNING"; WAITING_APPROVAL="WAITING_APPROVAL"; SUCCEEDED="SUCCEEDED"; FAILED="FAILED"; CANCELLED="CANCELLED"
class TaskStatus(str, enum.Enum):
    BLOCKED="BLOCKED"; READY="READY"; LEASED="LEASED"; SUCCEEDED="SUCCEEDED"; FAILED="FAILED"; CANCELLED="CANCELLED"

class Run(Base):
    __tablename__="runs"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    workflow: Mapped[str]=mapped_column(String(200))
    status: Mapped[RunStatus]=mapped_column(Enum(RunStatus), default=RunStatus.RUNNING)
    inputs: Mapped[dict]=mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class Task(Base):
    __tablename__="tasks"
    __table_args__=(UniqueConstraint("run_id","step_key"),)
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    run_id: Mapped[str]=mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    step_key: Mapped[str]=mapped_column(String(200))
    task_type: Mapped[str]=mapped_column(String(80))
    payload: Mapped[dict]=mapped_column(JSON, default=dict)
    status: Mapped[TaskStatus]=mapped_column(Enum(TaskStatus), default=TaskStatus.BLOCKED, index=True)
    attempts: Mapped[int]=mapped_column(Integer, default=0)
    max_attempts: Mapped[int]=mapped_column(Integer, default=3)
    lease_owner: Mapped[str|None]=mapped_column(String(200), nullable=True)
    result: Mapped[dict]=mapped_column(JSON, default=dict)
    error: Mapped[str|None]=mapped_column(Text, nullable=True)

class Dependency(Base):
    __tablename__="dependencies"
    __table_args__=(UniqueConstraint("task_id","depends_on_id"),)
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    task_id: Mapped[str]=mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    depends_on_id: Mapped[str]=mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))

class Approval(Base):
    __tablename__="approvals"
    __table_args__=(UniqueConstraint("run_id","gate_key"),)
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    run_id: Mapped[str]=mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    gate_key: Mapped[str]=mapped_column(String(200))
    status: Mapped[str]=mapped_column(String(30), default="PENDING")
    decided_by: Mapped[str|None]=mapped_column(String(200), nullable=True)

class Evidence(Base):
    __tablename__="evidence"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=lambda:str(uuid.uuid4()))
    run_id: Mapped[str]=mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))
    kind: Mapped[str]=mapped_column(String(100))
    uri: Mapped[str]=mapped_column(Text)
