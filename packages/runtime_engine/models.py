from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RuntimeCommand:
    service: str
    action: str
    command: tuple[str, ...]
    working_directory: Path
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeService:
    name: str
    working_directory: Path
    start: tuple[str, ...]
    stop: tuple[str, ...] = ()
    environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeProfile:
    name: str
    services: tuple[RuntimeService, ...]
