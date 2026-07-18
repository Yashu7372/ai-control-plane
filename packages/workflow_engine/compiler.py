from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .dag import DagNode, WorkflowDag


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    type: str
    depends_on: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    max_attempts: int = 3


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    version: int
    steps: tuple[WorkflowStep, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def dag(self) -> WorkflowDag:
        return WorkflowDag(
            [DagNode(step.id, step.depends_on) for step in self.steps]
        )


def compile_workflow(source: str | Path | dict[str, Any]) -> WorkflowDefinition:
    raw = _read_source(source)
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("workflow name is required")

    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("workflow must contain at least one step")

    steps: list[WorkflowStep] = []
    for index, item in enumerate(raw_steps):
        if not isinstance(item, dict):
            raise ValueError(f"step at index {index} must be an object")
        step_id = str(item.get("id", "")).strip()
        step_type = str(item.get("type", "")).strip()
        if not step_id or not step_type:
            raise ValueError(f"step at index {index} requires id and type")
        attempts = int(item.get("max_attempts", 3))
        if attempts < 1:
            raise ValueError(f"step '{step_id}' max_attempts must be positive")
        steps.append(
            WorkflowStep(
                id=step_id,
                type=step_type,
                depends_on=tuple(item.get("depends_on") or ()),
                payload=dict(item.get("payload") or {}),
                max_attempts=attempts,
            )
        )

    definition = WorkflowDefinition(
        name=name,
        version=int(raw.get("version", 1)),
        steps=tuple(steps),
        metadata=dict(raw.get("metadata") or {}),
    )
    definition.dag()
    return definition


def _read_source(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    path = Path(source)
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("workflow document must be an object")
    return parsed
