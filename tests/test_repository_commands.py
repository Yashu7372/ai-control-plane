import json
import sys
from pathlib import Path

from apps.cli.main import main
from packages.context_engine import RepositoryContextGenerator
from packages.repository_engine import AgentScaffolder, RepositoryAnalyzer
from packages.worker_engine import DurableTaskQueue


def test_scaffolder_creates_provider_files_without_overwriting(tmp_path: Path):
    existing = tmp_path / "AGENTS.md"
    existing.write_text("custom", encoding="utf-8")

    result = AgentScaffolder().materialize(tmp_path, {"codex", "claude", "copilot"})

    assert existing in result.skipped
    assert existing.read_text(encoding="utf-8") == "custom"
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".github/copilot-instructions.md").exists()
    common = tmp_path / ".ai-control-plane/common"
    assert (common / "README.md").exists()
    assert (common / "memory/HANDOFF.md").exists()
    assert (common / "governance/policy.yml").exists()
    assert (common / "workflows/feature-delivery.yml").exists()


def test_all_provider_instructions_reference_common_control_plane(tmp_path: Path):
    AgentScaffolder().materialize(tmp_path, {"codex", "claude", "copilot"})

    instruction_paths = (
        tmp_path / "AGENTS.md",
        tmp_path / "CLAUDE.md",
        tmp_path / ".claude/agents/repository-analyst.md",
        tmp_path / ".github/copilot-instructions.md",
        tmp_path / ".github/agents/repository-analyst.agent.md",
    )
    for path in instruction_paths:
        assert ".ai-control-plane/common" in path.read_text(encoding="utf-8")

    config = (tmp_path / ".ai-control-plane/config.yml").read_text(encoding="utf-8")
    assert "default: .ai-control-plane/common/workflows/feature-delivery.yml" in config


def test_repository_analyzer_detects_technology_and_ignores_build_output(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    source = tmp_path / "service/src/main"
    source.mkdir(parents=True)
    (source / "Application.java").write_text("class Application {}", encoding="utf-8")
    target = tmp_path / "target"
    target.mkdir()
    (target / "generated.java").write_text("generated", encoding="utf-8")

    report = RepositoryAnalyzer().analyze(tmp_path)

    assert report.file_count == 2
    assert report.technologies == ("Maven / Java",)
    assert report.extensions[".java"] == 1


def test_context_generator_prioritizes_agent_contract(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Rules\nRun service tests.", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Service\nAccount feature.", encoding="utf-8")

    pack = RepositoryContextGenerator(max_tokens=100).build(tmp_path, "implement account feature")

    assert pack.items[0].source == "AGENTS.md"
    assert {item.source for item in pack.items} == {"AGENTS.md", "README.md"}


def test_workflow_start_submits_normalized_run(tmp_path: Path, monkeypatch, capsys):
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        "name: sample\nsteps:\n  - id: context\n    type: context.generate\n",
        encoding="utf-8",
    )
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai-control-plane",
            "workflow-start",
            str(workflow),
            "--input",
            '{"ticket":"ABC-1"}',
            "--db",
            str(database),
        ],
    )

    main()

    result = json.loads(capsys.readouterr().out)
    task = DurableTaskQueue(database).get(result["tasks"]["context"])
    assert result["state"] == "CREATED"
    assert task.type == "context.generate"
    assert task.payload["input"] == {"ticket": "ABC-1"}
    assert task.payload["step_id"] == "context"


def test_workflow_start_preserves_dag_dependencies(tmp_path: Path, monkeypatch, capsys):
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        "name: sample\nsteps:\n"
        "  - id: context\n    type: context.generate\n"
        "  - id: implement\n    type: agent.implement\n    depends_on: [context]\n",
        encoding="utf-8",
    )
    database = tmp_path / "tasks.db"
    monkeypatch.setattr(sys, "argv", ["ai-control-plane", "workflow-start", str(workflow), "--db", str(database)])

    main()

    result = json.loads(capsys.readouterr().out)
    queue = DurableTaskQueue(database)
    context_id = result["tasks"]["context"]
    implement_id = result["tasks"]["implement"]
    assert queue.get(context_id).state == "READY"
    assert queue.get(implement_id).state == "BLOCKED"
    assert queue.dependencies(implement_id) == (context_id,)

    leased = queue.lease("test-worker")
    assert leased and leased.id == context_id
    queue.complete(context_id, "test-worker")
    assert queue.lease("test-worker").id == implement_id
