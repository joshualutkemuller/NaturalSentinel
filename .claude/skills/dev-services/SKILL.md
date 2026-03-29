---
description: Start or check Docker Compose services and verify all health endpoints. Use when starting local dev, debugging connectivity, or restarting services.
allowed-tools: Bash
---

Start or check NaturalSentinel Docker Compose services.

Arguments: $ARGUMENTS
- (none) — bring everything up and check health
- `--stop` — bring services down
- `--logs` — tail logs after startup
- `--restart <service>` — restart a single service

## Steps

1. Verify Docker is running: `docker info` — if it fails, tell the user and stop.

2. Based on arguments:
   - Default: `docker compose up -d`
   - `--stop`: `docker compose down`
   - `--restart <service>`: `docker compose restart <service>`

3. Show service status: `docker compose ps`

4. Probe each health endpoint:
   - Backend: `curl -sf http://localhost:8000/api/v1/utils/health-check/`
   - Frontend: `curl -sf http://localhost:5173 -o /dev/null -w "%{http_code}"`
   - Qdrant: `curl -sf http://localhost:6333/healthz`
   - Mailpit: `curl -sf http://localhost:1080 -o /dev/null -w "%{http_code}"`

5. For any unhealthy service, show its tail: `docker compose logs <service> --tail=50`

6. If `--logs` flag: `docker compose logs -f --tail=20`

Report which services are up, which failed, and log excerpts for failures.
