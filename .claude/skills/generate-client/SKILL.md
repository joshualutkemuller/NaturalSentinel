---
description: Regenerate the TypeScript API client from the backend OpenAPI schema. Run after any route, request model, or response model change.
allowed-tools: Bash, Read, Grep
---

Regenerate the frontend TypeScript API client from the backend's OpenAPI schema.

## Steps

1. From the repo root:
   ```
   bash scripts/generate-client.sh
   ```
   This script:
   - Imports `app.main` via `uv run python` and dumps OpenAPI JSON to `frontend/openapi.json`
   - Runs `bun run --filter frontend generate-client` (config: `frontend/openapi-ts.config.ts`)
   - Runs `bun run lint` (Biome)

2. Review changed files in `frontend/src/client/`:
   - `sdk.gen.ts` — service classes: `<Tag>Service`, methods from operationId
   - `schemas.gen.ts` — Pydantic models as TS types
   - `types.gen.ts` — additional types

3. If new routes were added, check that the new service class is imported in the relevant component.

4. TypeScript check:
   ```
   cd frontend && bunx tsc --noEmit
   ```

5. Report errors with file:line context and which schema change caused them.

## Notes

- Service naming: `{{tag}}Service` where tag = FastAPI `tags=[...]` value
- Methods: camelCase operationId with service name prefix removed
- The client uses axios; `OpenAPI.TOKEN` is set from localStorage — never hardcode auth in client calls
