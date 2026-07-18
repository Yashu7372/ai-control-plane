from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from packages.approval_engine import ApprovalStore
from packages.context_engine import RepositoryContextGenerator
from packages.governance_engine import PolicyEngine
from packages.knowledge_engine import DocumentIngestor, SQLiteKnowledgeStore
from packages.memory_engine import MemoryStore
from packages.repository_engine import AgentScaffolder, RepositoryAnalyzer
from packages.worker_engine import DurableTaskQueue
from packages.workflow_engine import compile_workflow


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai-control-plane")
    sub = parser.add_subparsers(dest="command", required=True)

    memory = sub.add_parser("memory-start")
    memory.add_argument("summary")

    policy = sub.add_parser("policy-check")
    policy.add_argument("action")
    policy.add_argument("--environment", default="local")
    policy.add_argument("--command", default="")

    workflow = sub.add_parser("workflow-validate")
    workflow.add_argument("path")

    workflow_start = sub.add_parser("workflow-start", help="validate and submit a workflow run")
    workflow_start.add_argument("path")
    workflow_start.add_argument("--input", default="{}", help="workflow input as a JSON object")
    workflow_start.add_argument("--db", default=".ai-control-plane/tasks.db")

    init = sub.add_parser("init", help="initialize portable AI agent repository files")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument(
        "--providers",
        nargs="+",
        choices=("claude", "codex", "copilot"),
        default=("claude", "codex", "copilot"),
    )
    init.add_argument("--force", action="store_true", help="replace existing generated files")
    init.add_argument("--dry-run", action="store_true")

    breakdown = sub.add_parser("repo-breakdown", help="generate repository structure reports")
    breakdown.add_argument("path", nargs="?", default=".")
    breakdown.add_argument("--output", default=".ai-control-plane/repository-breakdown.md")
    breakdown.add_argument("--json-output", default=".ai-control-plane/repository-breakdown.json")
    breakdown.add_argument("--max-files", type=int, default=100_000)

    context = sub.add_parser("context-generate", help="generate a task-focused Markdown context pack")
    context.add_argument("path", nargs="?", default=".")
    context.add_argument("--task", required=True)
    context.add_argument("--output", default=".ai-control-plane/context/CONTEXT.md")
    context.add_argument("--max-tokens", type=int, default=8_000)

    ingest = sub.add_parser("knowledge-ingest", help="ingest supported repository documents")
    ingest.add_argument("path", nargs="?", default=".")
    ingest.add_argument("--source")
    ingest.add_argument("--db", default=".ai-control-plane/knowledge.db")

    task = sub.add_parser("task-create")
    task.add_argument("type")
    task.add_argument("--payload", default="{}")
    task.add_argument("--db", default=".ai-control-plane/tasks.db")

    approval = sub.add_parser("approval-list")
    approval.add_argument("--db", default=".ai-control-plane/approvals.db")

    args = parser.parse_args()
    if args.command == "memory-start":
        print(MemoryStore().start_session(args.summary))
    elif args.command == "policy-check":
        print(json.dumps(PolicyEngine().decide(args.environment, args.action, args.command).__dict__, indent=2))
    elif args.command == "workflow-validate":
        definition = compile_workflow(Path(args.path))
        print(json.dumps({"name": definition.name, "order": definition.dag().topological_order()}, indent=2))
    elif args.command == "workflow-start":
        definition = compile_workflow(Path(args.path))
        workflow_input = _json_object(args.input, "--input")
        run_id = uuid4().hex
        queue = DurableTaskQueue(Path(args.db))
        step_by_id = {step.id: step for step in definition.steps}
        task_ids: dict[str, str] = {}
        for step_id in definition.dag().topological_order():
            step = step_by_id[step_id]
            task_ids[step_id] = queue.enqueue(
                step.type,
                {
                    **step.payload,
                    "run_id": run_id,
                    "workflow": definition.name,
                    "workflow_version": definition.version,
                    "step_id": step.id,
                    "depends_on": list(step.depends_on),
                    "input": workflow_input,
                    "workflow_metadata": definition.metadata,
                },
                max_attempts=step.max_attempts,
                depends_on=tuple(task_ids[dependency] for dependency in step.depends_on),
            )
        print(json.dumps({"run_id": run_id, "tasks": task_ids, "state": "CREATED"}, indent=2))
    elif args.command == "init":
        result = AgentScaffolder().materialize(
            Path(args.path), set(args.providers), force=args.force, dry_run=args.dry_run
        )
        print(
            json.dumps(
                {
                    "dry_run": args.dry_run,
                    "created": [str(path) for path in result.created],
                    "overwritten": [str(path) for path in result.overwritten],
                    "skipped": [str(path) for path in result.skipped],
                },
                indent=2,
            )
        )
    elif args.command == "repo-breakdown":
        root = Path(args.path).resolve()
        report = RepositoryAnalyzer(max_files=args.max_files).analyze(root)
        markdown_path = _resolve_output(root, args.output)
        json_path = _resolve_output(root, args.json_output)
        _write(markdown_path, report.as_markdown())
        _write(json_path, report.as_json())
        print(json.dumps({"markdown": str(markdown_path), "json": str(json_path), **report.as_dict()}, indent=2))
    elif args.command == "context-generate":
        root = Path(args.path).resolve()
        pack = RepositoryContextGenerator(max_tokens=args.max_tokens).build(root, args.task)
        output = _resolve_output(root, args.output)
        _write(output, pack.as_markdown())
        print(
            json.dumps(
                {
                    "output": str(output),
                    "selected": pack.metadata["selected_count"],
                    "token_estimate": pack.token_estimate,
                    "truncated": pack.truncated,
                },
                indent=2,
            )
        )
    elif args.command == "knowledge-ingest":
        path = Path(args.path).resolve()
        source = args.source or path.name
        nodes = DocumentIngestor().ingest_path(path, source)
        store = SQLiteKnowledgeStore(Path(args.db))
        for node in nodes:
            store.upsert_node(node)
        print(json.dumps({"source": source, "ingested": len(nodes), "db": args.db}, indent=2))
    elif args.command == "task-create":
        task_id = DurableTaskQueue(Path(args.db)).enqueue(args.type, json.loads(args.payload))
        print(json.dumps({"task_id": task_id}, indent=2))
    elif args.command == "approval-list":
        records = ApprovalStore(Path(args.db)).list_pending()
        print(json.dumps([asdict(record) for record in records], indent=2))


def _json_object(value: str, option: str) -> dict:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{option} must be a JSON object")
    return parsed


def _resolve_output(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
