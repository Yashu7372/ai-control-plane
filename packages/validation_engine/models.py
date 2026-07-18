from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceCheck:
    name: str
    path: str
    operator: str
    expected: Any


@dataclass(frozen=True)
class ValidationScenario:
    name: str
    checks: tuple[EvidenceCheck, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    scenario: str
    passed: bool
    checks: tuple[dict[str, Any], ...]
