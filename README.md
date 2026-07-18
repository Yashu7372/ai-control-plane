# AI Control Plane

A generalized, provider-neutral control plane for governed AI-assisted engineering workflows. This repository was migrated from the uploaded prototype while removing organization-specific names, paths, endpoints, credentials, and domain examples.

## Modules

- `packages/workflow_engine` — validated workflow compilation, DAG scheduling, run/task states
- `packages/context_engine` — ranked, deduplicated, token-budgeted context packs
- `packages/knowledge_engine` — document/test ingestion and durable SQLite graph storage
- `packages/memory_engine` — persistent session and handoff memory
- `packages/cache_engine` — durable cache contracts
- `packages/governance_engine` — deny-by-default policy decisions
- `packages/mcp_registry` — governed tool registration and routing
- `packages/model_router` — deterministic capability-based model selection
- `packages/workspace_engine` — dry-run-first task workspace planning
- `packages/runtime_engine` — governed service start/stop planning
- `packages/validation_engine` — offline evidence validation
- `packages/worker_engine` — durable leased task queue with retry
- `packages/approval_engine` — persistent approval lifecycle

## Applications

- `apps/api/main.py` — FastAPI control-plane API
- `apps/worker/main.py` — durable worker entrypoint
- `apps/cli/main.py` — operator CLI
- `apps/dashboard` — static operational dashboard

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn apps.api.main:app --reload
```

## Bootstrap and run a repository workflow

Install the package, then initialize a target repository with provider-neutral control-plane files plus native instructions for Codex, Claude, and GitHub Copilot:

```bash
ai-control-plane init /path/to/repository --dry-run
ai-control-plane init /path/to/repository
```

Existing instruction files are preserved unless `--force` is supplied. Limit generation to selected providers with `--providers codex copilot`.

Generate a deterministic repository inventory and a task-focused, token-budgeted context pack:

```bash
ai-control-plane repo-breakdown /path/to/repository
ai-control-plane context-generate /path/to/repository \
  --task "Implement ABC-123 without changing public API contracts"
```

The default outputs are `.ai-control-plane/repository-breakdown.{md,json}` and `.ai-control-plane/context/CONTEXT.md` inside the target repository.

Validate or submit the generated DAG workflow to the durable task queue:

```bash
ai-control-plane workflow-validate /path/to/repository/.ai-control-plane/workflows/feature-delivery.yml
ai-control-plane workflow-start /path/to/repository/.ai-control-plane/workflows/feature-delivery.yml \
  --input '{"ticket":"ABC-123","repository":"sample-service"}'
ai-control-plane-worker --once
```

Supported repository knowledge documents can also be persisted for later retrieval:

```bash
ai-control-plane knowledge-ingest /path/to/repository --source sample-service
```

Serve `apps/dashboard` with any static file server. By default it connects to `http://localhost:8000`.

## Safety model

The base platform does not execute arbitrary repository or shell commands. Runtime actions are converted into governed plans, task execution uses explicit adapters, workspace creation is dry-run-first, and sensitive values are redacted before persistence or display.
