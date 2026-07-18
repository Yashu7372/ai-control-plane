from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelRequest:
    capability: str
    prompt: str
    max_cost: float | None = None
    require_tools: bool = False
    require_json: bool = False


@dataclass(frozen=True)
class ModelProvider:
    name: str
    model: str
    capabilities: frozenset[str]
    cost_rank: int = 100
    supports_tools: bool = False
    supports_json: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    reason: str


class ModelRouter:
    def __init__(self, providers: list[ModelProvider]) -> None:
        self.providers = tuple(providers)

    def route(self, request: ModelRequest) -> ModelRoute:
        candidates = [
            provider
            for provider in self.providers
            if provider.enabled
            and request.capability in provider.capabilities
            and (not request.require_tools or provider.supports_tools)
            and (not request.require_json or provider.supports_json)
        ]
        if not candidates:
            raise LookupError(f"no model supports capability: {request.capability}")
        selected = min(candidates, key=lambda item: (item.cost_rank, item.name, item.model))
        return ModelRoute(
            provider=selected.name,
            model=selected.model,
            reason=f"lowest-ranked eligible provider for {request.capability}",
        )
