from __future__ import annotations

import re
from collections.abc import Iterable

from .models import ContextItem, ContextPack


class ContextPackBuilder:
    """Rank, deduplicate and budget retrieved material for one task."""

    def __init__(self, max_tokens: int = 8_000) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        self.max_tokens = max_tokens

    def build(self, task: str, candidates: Iterable[ContextItem]) -> ContextPack:
        ranked = sorted(candidates, key=lambda item: (-item.score, item.source, item.id))
        selected: list[ContextItem] = []
        seen: set[str] = set()
        used = 0
        truncated = False

        for item in ranked:
            fingerprint = self._fingerprint(item.content)
            if not fingerprint or fingerprint in seen:
                continue
            estimate = self._estimate_tokens(item.content)
            if used + estimate > self.max_tokens:
                truncated = True
                continue
            selected.append(item)
            seen.add(fingerprint)
            used += estimate

        return ContextPack(
            task=task.strip(),
            items=tuple(selected),
            token_estimate=used,
            truncated=truncated,
            metadata={"candidate_count": len(ranked), "selected_count": len(selected)},
        )

    @staticmethod
    def _estimate_tokens(value: str) -> int:
        # Deterministic provider-independent approximation suitable for budgeting.
        return max(1, (len(value) + 3) // 4)

    @staticmethod
    def _fingerprint(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())
