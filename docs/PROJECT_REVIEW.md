# Project Review - n8n-codex (2025-12-16)

## Snapshot
- Stack: Docker Compose runs n8n, Postgres, Claude Agent (FastAPI + Slack Socket Mode), and ChromaDB (`docker-compose.yml`).
- Workflows: `workflows/unifi_health_to_slack.json` (15m device health to Slack) and `workflows/unifi_best_practices_audit.json` (daily security audit with AI remediation).
- Agent: `claude-agent/src` uses Anthropic Messages API with UniFi tools, confirmation flow, Duo MFA hooks, and Chroma-backed knowledge base.
- Docs: Setup in `README.md`, extensive session history in `SESSION_NOTES.md`, and key rotation plan in `docs/N8N_ENCRYPTION_KEY_ROTATION.md`.

## Strengths
- Clear onboarding (`README.md`, `.env.example`) and compose healthchecks for n8n/Postgres/Claude Agent.
- Agent tooling covers read and admin actions with confirmation gates (`claude-agent/src/agent/tools.py`) and CSRF-aware UniFi client (`claude-agent/src/unifi/controller_api.py`).
- Knowledge base shipped as Markdown (`claude-agent/knowledge/*.md`) and indexed to ChromaDB on startup (`knowledge/embeddings.py`).
- Workflows already structured for token efficiency (AI only runs on issues) and Slack alerts are in place.

## Gaps / Risks
- Security defaults: `.env.example` ships weak placeholders (`POSTGRES_PASSWORD=change-me`, `N8N_ENCRYPTION_KEY=generate-a-32-char-secret`), and both UniFi clients disable TLS verification by default (`verify_ssl=False` in `integration_api.py`, `controller_api.py`).
- Testing: `claude-agent/tests/` is empty; no automated coverage for UniFi clients, tools, or FastAPI routes.
- CI/CD: No pipeline to lint/test/build images; regressions would be caught only at runtime.
- Observability: Logging is basic stdout; no structured logs, metrics, or alerting on agent errors (e.g., Chroma init failures fall back silently).
- Workflow robustness: n8n flows rely on manual credential wiring; no validation step to fail fast when env vars/credentials are missing or Slack/unifi endpoints are unreachable.

## Recommendations (prioritized)
1) **Lock down secrets/TLS**
   - Require real values for `POSTGRES_PASSWORD` and `N8N_ENCRYPTION_KEY` (mirror key rotation doc) before boot; optionally enforce via startup check in FastAPI lifespan.
   - Add `UNIFI_VERIFY_SSL` env and pass through to UniFi clients; default to `True` for prod and document self-signed override.
   - Consider Docker secrets/`docker compose --env-file` for anything long-lived.

2) **Add tests + fixtures**
   - Use `pytest` + `respx` to unit test UniFi clients (200/401/403 flows, CSRF refresh) and tool behaviors (confirmation-required branches, safe commands).
   - Add FastAPI route tests with httpx `AsyncClient` to verify `/api/health`, `/api/analyze/*`, `/api/query` happy-path and error handling.
   - Include minimal sample JSON fixtures for UniFi responses to avoid hitting live controllers in CI.

3) **Build CI guardrails**
   - GitHub Actions workflow: cache pip, run `ruff` + `pytest`, then build `claude-agent` image; optional `docker compose config` to validate stack syntax.
   - Publish built image to GHCR for reuse in deployment and local testing.

4) **Improve observability**
   - Switch to structured logging (JSON) with request IDs and tool call traces; add log redaction for tokens.
   - Add `/api/ready` that asserts Anthropic key present and Chroma reachable; surface Chroma indexing stats in health output.
   - Emit basic metrics (requests, tool executions, UniFi error counts) via Prometheus or StatsD sink.

5) **Harden workflows**
   - Add a preflight Function node to both workflows that checks required env vars/credentials and short-circuits with a Slack warning when missing.
   - Rate-limit or dedupe Slack alerts (e.g., store last alert hash in n8n static data) to avoid alert storms on flapping devices.
   - Capture workflow execution outputs (sanitized) in `SESSION_NOTES.md` or a `/docs/runbook.md` section for future regressions.

6) **Operational polish**
   - Provide a `make` target (or scripts) for `compose up`, `compose down`, `logs`, and `pytest` to standardize local workflows.
   - Add a short `docs/DEPLOY_CHECKLIST.md` covering env validation, port exposure, and Slack app scopes for repeatable deploys.
