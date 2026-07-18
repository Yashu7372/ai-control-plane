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
            root / ".ai-control-plane" / "common" / "README.md": _COMMON,
            root / ".ai-control-plane" / "common" / "memory" / "HANDOFF.md": _HANDOFF,
            root / ".ai-control-plane" / "common" / "governance" / "policy.yml": _GOVERNANCE,
            root / ".ai-control-plane" / "common" / "workflows" / "feature-delivery.yml": _WORKFLOW,
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

## Required startup sequence

Before planning, editing, or running tools:

1. Read `.ai-control-plane/common/README.md`.
2. Read `.ai-control-plane/common/governance/policy.yml` and obey its approval boundaries.
3. Read the selected workflow under `.ai-control-plane/common/workflows/`.
4. Read `.ai-control-plane/common/memory/HANDOFF.md` for prior decisions and unfinished work.
5. Read `.ai-control-plane/context/CONTEXT.md` and the repository breakdown when present.

The common folder is shared control-plane state. Do not create provider-specific memory,
governance, or workflow copies when a common definition exists.

## Working agreement

- Preserve existing behavior and keep changes within the requested task.
- Run the smallest relevant tests first, then the full validation suite.
- Do not commit credentials, generated secrets, build output, or local databases.
- Update `.ai-control-plane/common/memory/HANDOFF.md` with decisions, validation evidence,
  unfinished work, and unresolved risks before handing off.
"""

_CLAUDE = """# Claude Repository Instructions

Follow `AGENTS.md` when present. Treat `.ai-control-plane/common/` as the shared source of truth.
Before editing, read its `README.md`, governance policy, selected workflow, and memory handoff,
then read `.ai-control-plane/context/CONTEXT.md`. Use
`.ai-control-plane/common/workflows/feature-delivery.yml` for the default delivery stages.
Update `.ai-control-plane/common/memory/HANDOFF.md` before handing off.
Never execute destructive or production-changing operations without explicit approval.
"""

_CLAUDE_AGENT = """---
name: repository-analyst
description: Maps repository structure, dependencies, entry points, tests, and delivery risks.
tools: Read, Glob, Grep
---

Analyze only. Return a concise repository breakdown, relevant files, dependencies, tests, and risks.
Read `.ai-control-plane/common/README.md` and its governance, workflow, and memory references first.
Do not modify files.
"""

_COPILOT = """# Copilot repository instructions

- Treat `AGENTS.md` as the shared engineering contract when it exists.
- Treat `.ai-control-plane/common/` as the single source for memory, governance, and workflows.
- Read the common README, governance policy, selected workflow, memory handoff, and task context
  before implementing a task.
- Prefer existing patterns and dependencies; avoid unrelated refactors.
- Add or update tests and report the exact validation commands executed.
- Update `.ai-control-plane/common/memory/HANDOFF.md` before completing the task.
- Never include secrets, credentials, or sensitive operational data in generated output.
"""

_COPILOT_AGENT = """---
name: repository-analyst
description: Produce a read-only repository and task context assessment.
tools: ['search', 'read']
---

Read `.ai-control-plane/common/README.md` first. Map modules, dependencies, entry points,
tests, and task-relevant risks. Do not edit files.
"""

_CONFIG = """version: 1
repository:
  breakdown: .ai-control-plane/repository-breakdown.md
common:
  root: .ai-control-plane/common
  memory: .ai-control-plane/common/memory
  governance: .ai-control-plane/common/governance
  workflows: .ai-control-plane/common/workflows
context:
  output: .ai-control-plane/context/CONTEXT.md
  max_tokens: 8000
workflow:
  default: .ai-control-plane/common/workflows/feature-delivery.yml
state:
  task_db: .ai-control-plane/tasks.db
"""

_COMMON = """# Common Agent Control Plane

This directory is the provider-neutral source of truth for every coding agent.

Read shared material in this order before starting work:

1. `governance/policy.yml` — safety boundaries and approval requirements.
2. `workflows/` — the selected delivery lifecycle and dependency order.
3. `memory/HANDOFF.md` — prior decisions, current state, and unfinished work.
4. `../context/CONTEXT.md` — task-specific retrieved context, when present.

Claude, Codex, Copilot, and other providers must reuse these definitions. Provider-specific
instruction files may add interface guidance, but must not redefine or bypass common governance,
workflow dependencies, or shared memory.
"""

_HANDOFF = """# Shared Agent Handoff

## Current objective

Not set.

## Decisions and constraints

- None recorded.

## Validation evidence

- None recorded.

## Unfinished work and risks

- None recorded.
"""

_GOVERNANCE = """version: 1
default: deny
read_only:
  allowed: true
approvals_required:
  - destructive_action
  - production_write
  - external_publish
prohibited:
  - expose_secrets
  - bypass_validation
  - weaken_security_controls
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
