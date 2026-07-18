from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from packages.approval_engine import ApprovalStore
from packages.model_router import ModelProvider, ModelRequest, ModelRouter
from packages.worker_engine import DurableTaskQueue

DATA_DIR = Path(os.getenv("AI_CONTROL_PLANE_DATA", ".ai-control-plane"))
queue = DurableTaskQueue(DATA_DIR / "tasks.db")
approvals = ApprovalStore(DATA_DIR / "approvals.db")
router = ModelRouter(
    [
        ModelProvider("default", "general", frozenset({"planning", "coding", "analysis"}), 10, True, True),
    ]
)
app = FastAPI(title="AI Control Plane", version="0.1.0")


class TaskCreate(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)
    max_attempts: int = 3


class ApprovalCreate(BaseModel):
    action: str
    resource: str
    requester: str
    payload: dict = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    approved: bool
    decided_by: str
    reason: str | None = None


class RouteRequest(BaseModel):
    capability: str
    prompt: str
    require_tools: bool = False
    require_json: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "UP"}


@app.post("/tasks", status_code=201)
def create_task(request: TaskCreate) -> dict[str, str]:
    return {"task_id": queue.enqueue(request.type, request.payload, request.max_attempts)}


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    try:
        return asdict(queue.get(task_id))
    except KeyError as exc:
        raise HTTPException(404, "task not found") from exc


@app.post("/tasks/{task_id}/retry")
def retry_task(task_id: str) -> dict[str, str]:
    try:
        queue.retry(task_id)
        return {"state": "READY"}
    except KeyError as exc:
        raise HTTPException(404, "task not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/approvals", status_code=201)
def create_approval(request: ApprovalCreate) -> dict[str, str]:
    return {"approval_id": approvals.request(request.action, request.resource, request.requester, request.payload)}


@app.get("/approvals")
def list_approvals() -> list[dict]:
    return [asdict(item) for item in approvals.list_pending()]


@app.post("/approvals/{approval_id}/decision")
def decide_approval(approval_id: str, request: ApprovalDecision) -> dict:
    try:
        return asdict(approvals.decide(approval_id, request.approved, request.decided_by, request.reason))
    except KeyError as exc:
        raise HTTPException(404, "approval not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/models/route")
def route_model(request: RouteRequest) -> dict:
    try:
        return asdict(router.route(ModelRequest(**request.model_dump())))
    except LookupError as exc:
        raise HTTPException(422, str(exc)) from exc
