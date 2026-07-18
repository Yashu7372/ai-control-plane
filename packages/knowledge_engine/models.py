from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class KnowledgeNode:
    id: str
    type: str
    name: str
    source: str
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeEdge:
    source_id: str
    target_id: str
    type: str
    metadata: dict[str, Any] = field(default_factory=dict)
