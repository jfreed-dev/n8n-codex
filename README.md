# n8n + OpenAI Codex + Unifi health

Opinionated starter to run n8n in Docker with PostgreSQL, wire OpenAI Codex for inference, and ship a Unifi health/config monitor that alerts Slack.

## What you get
- `docker-compose.yml` to run n8n + Postgres with persistent volumes.
- `.env.example` for all required secrets.
- `workflows/openai_codex_inference.json` – template workflow for calling OpenAI Codex via HTTP node.
- `workflows/unifi_health_to_slack.json` – scheduled Unifi health/config poller with Slack alerting.

## Prereqs
- Docker + docker compose
- OpenAI API key (Codex/completions access)
- Unifi API token with read scope (`Settings > System > Advanced > API Access` on recent controllers)
- Slack Bot token (chat:write scope) and signing secret

## Setup
1) Copy env template and edit:
```bash
cp .env.example .env
# fill POSTGRES_*, N8N_HOST, WEBHOOK_URL, N8N_ENCRYPTION_KEY
# add OPENAI_API_KEY / OPENAI_MODEL (defaults to code-davinci-002)
# add UNIFI_BASE_URL / UNIFI_API_TOKEN / UNIFI_SITE
# add SLACK_BOT_TOKEN / SLACK_SIGNING_SECRET / SLACK_CHANNEL
```

2) Start the stack:
```bash
docker compose up -d
```
- n8n UI: http://localhost:5678
- Data persists in `.n8n_data` and the named Postgres volume.

3) Import workflows in n8n UI:
- `Import from File` → pick `workflows/openai_codex_inference.json`
- `Import from File` → pick `workflows/unifi_health_to_slack.json`

4) Wire credentials
- OpenAI: set env vars; HTTP node uses headers `Authorization: Bearer {{ $env.OPENAI_API_KEY }}` and model from `OPENAI_MODEL`.
- Unifi: supply `UNIFI_BASE_URL`, `UNIFI_API_TOKEN`, `UNIFI_SITE`. If your cert is self-signed, `allowUnauthorizedCerts` is enabled in the HTTP nodes.
- Slack: incoming webhook URL; optional `SLACK_CHANNEL` overrides the default on some webhook apps.

## Workflow notes
### OpenAI Codex template
Manual trigger → Set Prompt → HTTP Request to `/v1/completions` → Function that returns `{ prompt, completion }`. Swap `Set Prompt` for any upstream node to pipe real prompts.

### Unifi health to Slack
Uses the UniFi Network Integration API with `X-API-KEY`.
- Cron (every 15m) → Get Sites (`/proxy/network/integration/v1/sites`) → pick site by `UNIFI_SITE` (defaults to `default`) → fetch health/devices for that site → summarize degraded/offline/upgrade-needed states → Slack message via chat.postMessage (bot token) only when degraded. Tweak the Function node to change severity filters or add config checks.

## Customization ideas
- Replace HTTP Slack call with the native Slack node using OAuth (reuse the same bot token).
- Add alert throttling with `Move` + `Wait` or a Redis-based rate limiter.
- Add a Codex "advisor" node after Unifi fetches to produce human-readable remediation steps.
- Expose n8n behind HTTPS by putting Traefik/Caddy in front if you'll run it remotely.

## Running locally
- Stop stack: `docker compose down`
- View logs: `docker compose logs -f n8n`

## Security
- Set a strong `N8N_ENCRYPTION_KEY` before first launch; changing it later invalidates saved credentials.
- If running on the internet, place n8n behind auth (reverse proxy + basic auth/OIDC) and use HTTPS.
