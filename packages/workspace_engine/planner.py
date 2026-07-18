from __future__ import annotations

import json
import re
from pathlib import Path

from .models import RepositorySelection, WorkspacePlan


class WorkspacePlanner:
    VALID_MODES = {"editable", "reference", "readonly"}

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def plan(self, task_id: str, repositories: list[RepositorySelection]) -> WorkspacePlan:
        safe_task = re.sub(r"[^A-Za-z0-9_.-]+", "-", task_id).strip("-")
        if not safe_task:
            raise ValueError("task_id must contain at least one safe character")
        if not repositories:
            raise ValueError("at least one repository is required")

        seen: set[str] = set()
        normalized: list[RepositorySelection] = []
        for repository in repositories:
            if repository.name in seen:
                raise ValueError(f"duplicate repository: {repository.name}")
            if repository.mode not in self.VALID_MODES:
                raise ValueError(f"unsupported repository mode: {repository.mode}")
            if not repository.source_path.exists():
                raise FileNotFoundError(repository.source_path)
            seen.add(repository.name)
            normalized.append(repository)

        root = self.workspace_root / safe_task
        branch_name = f"task/{safe_task}"
        files = {
            "workspace.json": json.dumps(
                {
                    "taskId": safe_task,
                    "branch": branch_name,
                    "repositories": [
                        {
                            "name": item.name,
                            "source": str(item.source_path.resolve()),
                            "mode": item.mode,
                            "baseRef": item.base_ref,
                        }
                        for item in normalized
                    ],
                },
                indent=2,
            ),
            "AI_CONTEXT.md": (
                f"# Task Context\n\nTask: `{safe_task}`\n\n"
                "This workspace was generated from a reviewed repository plan.\n"
            ),
        }
        return WorkspacePlan(
            task_id=safe_task,
            root=root,
            branch_name=branch_name,
            repositories=tuple(normalized),
            files=files,
        )

    def materialize(self, plan: WorkspacePlan, dry_run: bool = True) -> list[Path]:
        targets = [plan.root / name for name in plan.files]
        if dry_run:
            return targets
        plan.root.mkdir(parents=True, exist_ok=True)
        for relative, content in plan.files.items():
            target = plan.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return targets
