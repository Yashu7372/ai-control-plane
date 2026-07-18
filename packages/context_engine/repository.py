from __future__ import annotations

import re
from pathlib import Path

from .builder import ContextPackBuilder
from .models import ContextItem, ContextPack


IGNORED_DIRECTORIES = {".git", ".venv", "build", "dist", "node_modules", "target", "venv"}
PREFERRED_NAMES = {
    "AGENTS.md": 1.0,
    "CLAUDE.md": 0.98,
    "AI_CONTEXT.md": 0.96,
    "README.md": 0.90,
    "repository-breakdown.md": 0.92,
}


class RepositoryContextGenerator:
    """Build a task-focused context pack from bounded repository documentation."""

    def __init__(self, max_tokens: int = 8_000, max_file_bytes: int = 128_000) -> None:
        self.builder = ContextPackBuilder(max_tokens=max_tokens)
        self.max_file_bytes = max_file_bytes

    def build(self, root: Path, task: str) -> ContextPack:
        root = root.resolve()
        if not root.is_dir():
            raise NotADirectoryError(root)
        candidates: list[ContextItem] = []
        for path in sorted(root.rglob("*.md")):
            relative = path.relative_to(root)
            if any(part in IGNORED_DIRECTORIES for part in relative.parts):
                continue
            try:
                if path.stat().st_size > self.max_file_bytes:
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if not content:
                continue
            candidates.append(
                ContextItem(
                    id=str(relative),
                    source=str(relative),
                    title=relative.name,
                    content=content,
                    score=self._score(relative, content, task),
                    metadata={"path": str(relative)},
                )
            )
        return self.builder.build(task, candidates)

    @staticmethod
    def _score(path: Path, content: str, task: str) -> float:
        base = PREFERRED_NAMES.get(path.name, 0.55)
        if "docs" in {part.lower() for part in path.parts}:
            base += 0.05
        task_terms = {term for term in re.findall(r"[a-z0-9_-]{3,}", task.lower())}
        if not task_terms:
            return min(base, 1.0)
        searchable = f"{path} {content[:20_000]}".lower()
        matches = sum(1 for term in task_terms if term in searchable)
        return min(1.0, base + 0.04 * matches)
