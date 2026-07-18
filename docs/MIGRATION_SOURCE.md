# Prototype Migration Source

The implementation on this branch is derived from the uploaded control-plane prototype. The source modules included workflow orchestration, governed MCP dispatch, persistent memory, caching, knowledge ingestion, context assembly, workspace creation, runtime validation and a dashboard.

Migration rules:

1. Preserve reusable behavior before reorganizing directories.
2. Remove organization-specific names, local user paths, credentials and proprietary domain examples.
3. Convert domain-bound adapters into optional provider plugins.
4. Keep dangerous execution deny-by-default.
5. Never label a module implemented until code and tests exist on this branch.
