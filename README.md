# AI Control Plane

This branch contains the generalized form of the uploaded control-plane prototype. The implementation is being migrated from the prototype, not regenerated from an empty scaffold.

## Structure

- `apps/control-plane-api` — HTTP control-plane entrypoint
- `apps/worker` — durable worker entrypoint
- `apps/cli` — operator CLI
- `packages/workflow-engine` — workflow orchestration and task state
- `packages/memory-engine` — persistent session, event, evidence and handoff memory
- `packages/governance-engine` — deny-by-default execution policy
- `packages/mcp-registry` — tool registration and governed dispatch
- `packages/cache-engine` — durable cache contracts
- `packages/common` — redaction and shared utilities

Additional prototype modules—context, knowledge, workspace, runtime, validation and dashboard—will be migrated in follow-up commits on this same branch.

## Privacy

Organization-specific names, paths, data models, credentials, internal endpoints and proprietary examples are intentionally excluded or rewritten as generic examples.
