from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextItem:
    id: str
    source: str
    title: str
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextPack:
    task: str
    items: tuple[ContextItem, ...]
    token_estimate: int
    truncated: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_markdown(self) -> str:
        sections = [f"# Context Pack\n\nTask: {self.task}"]
        for item in self.items:
            sections.append(
                f"## {item.title}\n\n"
                f"Source: `{item.source}`\n"
                f"Score: {item.score:.3f}\n\n"
                f"{item.content.strip()}"
            )
        return "\n\n".join(sections) + "\n"
