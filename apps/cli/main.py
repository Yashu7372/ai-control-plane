from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from packages.approval_engine import ApprovalStore
from packages.governance_engine import PolicyEngine
from packages.memory_engine import MemoryStore
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
    elif args.command == "task-create":
        task_id = DurableTaskQueue(Path(args.db)).enqueue(args.type, json.loads(args.payload))
        print(json.dumps({"task_id": task_id}, indent=2))
    elif args.command == "approval-list":
        records = ApprovalStore(Path(args.db)).list_pending()
        print(json.dumps([asdict(record) for record in records], indent=2))


if __name__ == "__main__":
    main()
