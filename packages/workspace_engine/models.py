from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RepositorySelection:
    name: str
    source_path: Path
    mode: str = "editable"
    base_ref: str = "main"


@dataclass(frozen=True)
class WorkspacePlan:
    task_id: str
    root: Path
    branch_name: str
    repositories: tuple[RepositorySelection, ...]
    files: dict[str, str] = field(default_factory=dict)
