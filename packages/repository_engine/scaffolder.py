from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_PROVIDERS = {"claude", "codex", "copilot"}


@dataclass(frozen=True)
class ScaffoldResult:
    created: tuple[Path, ...]
    skipped: tuple[Path, ...]
    overwritten: tuple[Path, ...]


class AgentScaffolder:
    """Create portable agent instructions and a starter control-plane workflow."""

    def plan(self, root: Path, providers: set[str]) -> dict[Path, str]:
        unknown = providers - SUPPORTED_PROVIDERS
        if unknown:
            raise ValueError(f"unsupported providers: {', '.join(sorted(unknown))}")
        if not providers:
            raise ValueError("at least one provider is required")

        files: dict[Path, str] = {
            root / ".ai-control-plane" / "config.yml": _CONFIG,
            root / ".ai-control-plane" / "workflows" / "feature-delivery.yml": _WORKFLOW,
        }
        if "codex" in providers:
            files[root / "AGENTS.md"] = _AGENTS
        if "claude" in providers:
            files[root / "CLAUDE.md"] = _CLAUDE
            files[root / ".claude" / "agents" / "repository-analyst.md"] = _CLAUDE_AGENT
        if "copilot" in providers:
            files[root / ".github" / "copilot-instructions.md"] = _COPILOT
            files[root / ".github" / "agents" / "repository-analyst.agent.md"] = _COPILOT_AGENT
        return files

    def materialize(
        self,
        root: Path,
        providers: set[str],
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> ScaffoldResult:
        root = root.resolve()
        if root.exists() and not root.is_dir():
            raise NotADirectoryError(root)
        planned = self.plan(root, providers)
        created: list[Path] = []
        skipped: list[Path] = []
        overwritten: list[Path] = []
        for target, content in planned.items():
            if target.exists() and not force:
                skipped.append(target)
                continue
            bucket = overwritten if target.exists() else created
            bucket.append(target)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        return ScaffoldResult(tuple(created), tuple(skipped), tuple(overwritten))


_AGENTS = """# Repository Agent Instructions

## Working agreement

- Read `.ai-control-plane/context/CONTEXT.md` and the repository breakdown before planning.
- Preserve existing behavior and keep changes within the requested task.
- Run the smallest relevant tests first, then the full validation suite.
- Do not commit credentials, generated secrets, build output, or local databases.
- Record assumptions, validation evidence, and unresolved risks in the handoff.
"""

_CLAUDE = """# Claude Repository Instructions

Follow `AGENTS.md` when present. Use `.ai-control-plane/workflows/feature-delivery.yml` for delivery stages.
Inspect `.ai-control-plane/context/CONTEXT.md` before editing and keep a concise evidence-based handoff.
Never execute destructive or production-changing operations without explicit approval.
"""

_CLAUDE_AGENT = """---
name: repository-analyst
description: Maps repository structure, dependencies, entry points, tests, and delivery risks.
tools: Read, Glob, Grep
---

Analyze only. Return a concise repository breakdown, relevant files, dependencies, tests, and risks.
Do not modify files.
"""

_COPILOT = """# Copilot repository instructions

- Treat `AGENTS.md` as the shared engineering contract when it exists.
- Read `.ai-control-plane/context/CONTEXT.md` before implementing a task.
- Prefer existing patterns and dependencies; avoid unrelated refactors.
- Add or update tests and report the exact validation commands executed.
- Never include secrets, credentials, or sensitive operational data in generated output.
"""

_COPILOT_AGENT = """---
name: repository-analyst
description: Produce a read-only repository and task context assessment.
tools: ['search', 'read']
---

Map modules, dependencies, entry points, tests, and task-relevant risks. Do not edit files.
"""

_CONFIG = """version: 1
repository:
  breakdown: .ai-control-plane/repository-breakdown.md
context:
  output: .ai-control-plane/context/CONTEXT.md
  max_tokens: 8000
workflow:
  default: .ai-control-plane/workflows/feature-delivery.yml
state:
  task_db: .ai-control-plane/tasks.db
"""

_WORKFLOW = """name: feature-delivery
version: 1
steps:
  - id: repository-breakdown
    type: repository.breakdown
  - id: context
    type: context.generate
    depends_on: [repository-breakdown]
  - id: plan
    type: agent.plan
    depends_on: [context]
  - id: approval
    type: approval.request
    depends_on: [plan]
  - id: implement
    type: agent.implement
    depends_on: [approval]
  - id: validate
    type: validation.run
    depends_on: [implement]
"""
