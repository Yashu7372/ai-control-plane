import os
from pathlib import Path

os.environ.setdefault("AI_CONTROL_PLANE_DB", f"sqlite:///{Path('/tmp')/'ai-control-plane-test.sqlite'}")

from fastapi.testclient import TestClient
from control_plane.api import app
from control_plane.compiler import compile_workflow
from control_plane.engine import Engine
from control_plane.worker import run_once


def test_end_to_end():
    run_id = compile_workflow("workflows/demo.yaml", {"story": "demo"})
    while run_once():
        state = Engine().get_run(run_id)
        if state["status"] == "WAITING_APPROVAL":
            break
    Engine().decide(run_id, "approval", True, "tester")
    while run_once():
        pass
    assert Engine().get_run(run_id)["status"] == "SUCCEEDED"


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "UP"}
