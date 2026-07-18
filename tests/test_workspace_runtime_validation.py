from pathlib import Path

from packages.runtime_engine import RuntimePlanner, RuntimeProfile, RuntimeService
from packages.validation_engine import EvidenceCheck, EvidenceValidator, ValidationScenario
from packages.workspace_engine import RepositorySelection, WorkspacePlanner


def test_workspace_planner_is_dry_run_first(tmp_path: Path):
    repository = tmp_path / "repo"
    repository.mkdir()
    planner = WorkspacePlanner(tmp_path / "workspaces")
    plan = planner.plan(
        "TASK-101",
        [RepositorySelection("repo", repository, "editable", "main")],
    )
    targets = planner.materialize(plan, dry_run=True)
    assert not plan.root.exists()
    assert plan.branch_name == "task/TASK-101"
    assert targets[0].parent == plan.root


def test_runtime_planner_requires_approval_for_start(tmp_path: Path):
    profile = RuntimeProfile(
        "sample",
        (
            RuntimeService(
                name="api",
                working_directory=tmp_path,
                start=("python", "-m", "api"),
                stop=("python", "-m", "api", "--stop"),
            ),
        ),
    )
    commands = RuntimePlanner().plan_start(profile, "test")
    assert commands[0].action == "approval_required"


def test_validation_engine_compares_offline_evidence():
    scenario = ValidationScenario(
        "api-check",
        (
            EvidenceCheck("status", "response.status", "eq", 200),
            EvidenceCheck("body", "response.body", "contains", "ready"),
        ),
    )
    result = EvidenceValidator().validate(
        scenario,
        {"response": {"status": 200, "body": "service ready"}},
    )
    assert result.passed
    assert all(check["passed"] for check in result.checks)
