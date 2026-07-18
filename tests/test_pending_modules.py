from pathlib import Path

from fastapi.testclient import TestClient

from packages.approval_engine import ApprovalStore
from packages.model_router import ModelProvider, ModelRequest, ModelRouter
from packages.worker_engine import DurableTaskQueue


def test_model_router_selects_lowest_ranked_eligible_provider():
    router = ModelRouter(
        [
            ModelProvider("expensive", "large", frozenset({"coding"}), 50, True, True),
            ModelProvider("cheap", "small", frozenset({"coding"}), 10, False, True),
        ]
    )
    route = router.route(ModelRequest("coding", "implement", require_json=True))
    assert route.provider == "cheap"


def test_durable_queue_retries_and_completes(tmp_path: Path):
    queue = DurableTaskQueue(tmp_path / "tasks.db")
    task_id = queue.enqueue("validate", {"target": "api"}, max_attempts=2)
    leased = queue.lease("worker-a")
    assert leased is not None and leased.id == task_id
    queue.fail(task_id, "worker-a", "temporary")
    assert queue.get(task_id).state == "READY"
    leased = queue.lease("worker-a")
    assert leased is not None
    queue.complete(task_id, "worker-a")
    assert queue.get(task_id).state == "SUCCEEDED"


def test_approval_lifecycle(tmp_path: Path):
    store = ApprovalStore(tmp_path / "approvals.db")
    approval_id = store.request("runtime.start", "sample-api", "developer")
    assert store.get(approval_id).state == "PENDING"
    record = store.decide(approval_id, True, "reviewer", "approved for local test")
    assert record.state == "APPROVED"
    assert store.list_pending() == []


def test_api_health_and_task_creation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AI_CONTROL_PLANE_DATA", str(tmp_path))
    import importlib
    import apps.api.main as api_module

    api_module = importlib.reload(api_module)
    client = TestClient(api_module.app)
    assert client.get("/health").json() == {"status": "UP"}
    created = client.post("/tasks", json={"type": "validation", "payload": {"id": 1}})
    assert created.status_code == 201
    task_id = created.json()["task_id"]
    assert client.get(f"/tasks/{task_id}").json()["state"] == "READY"
