# n8n + Claude Agent + UniFi Health

[![CI](https://github.com/jfreed-dev/n8n-codex/actions/workflows/ci.yml/badge.svg)](https://github.com/jfreed-dev/n8n-codex/actions/workflows/ci.yml)

Opinionated starter to run n8n in Docker with PostgreSQL, a Claude-powered AI agent for network intelligence, and UniFi health/config monitoring with Slack alerts.

## What you get
- `docker-compose.yml` to run n8n + Postgres + Claude Agent + ChromaDB with persistent volumes.
- `.env.example` for all required secrets.
- `claude-agent/` – AI-powered UniFi network expert with Slack integration and HTTP API.
- `workflows/unifi_health_to_slack.json` – scheduled UniFi health poller with AI analysis and Slack alerting.
- `workflows/unifi_best_practices_audit.json` – daily security audit with AI recommendations.
- `ARCHITECTURE.md` – visual Mermaid diagrams of service topology, data flows, and component interactions.

## Prereqs
- Docker + docker compose
- Anthropic API key (for Claude Agent)
- UniFi API token with read scope (`Settings > System > Advanced > API Access` on recent controllers)
- UniFi controller credentials (username/password) for best practices audit
- Slack Bot token (chat:write scope) and signing secret

## Setup
1) Copy env template and edit:
```bash
cp .env.example .env
# fill POSTGRES_*, N8N_HOST, WEBHOOK_URL, N8N_ENCRYPTION_KEY
# add ANTHROPIC_API_KEY for Claude Agent
# add UNIFI_BASE_URL / UNIFI_API_TOKEN / UNIFI_SITE (Integration API)
# add UNIFI_USERNAME / UNIFI_PASSWORD (Local Controller API for audits)
# add SLACK_BOT_TOKEN / SLACK_APP_TOKEN / SLACK_SIGNING_SECRET / SLACK_CHANNEL
```

2) Start the stack:
```bash
docker compose up -d
```
- n8n UI: http://localhost:5678
- Claude Agent API: http://localhost:8080
- ChromaDB: http://localhost:8000
- Data persists in `.n8n_data`, `chromadb_data/`, and the named Postgres volume.

3) Import workflows in n8n UI:
- `Import from File` → pick `workflows/unifi_health_to_slack.json`
- `Import from File` → pick `workflows/unifi_best_practices_audit.json`

4) Wire credentials
- UniFi Integration API: supply `UNIFI_BASE_URL`, `UNIFI_API_TOKEN`, `UNIFI_SITE`. If your cert is self-signed, `allowUnauthorizedCerts` is enabled in the HTTP nodes.
- UniFi Local Controller API: supply `UNIFI_USERNAME`, `UNIFI_PASSWORD` for cookie-based auth.
- Slack: bot token for chat.postMessage; app token for Socket Mode (Claude Agent).

## Workflow notes
### Claude Agent
The Claude Agent service provides AI-powered UniFi network intelligence:
- **Slack Q&A**: @mention the bot or DM to ask questions about your network
- **HTTP API**: Endpoints for n8n workflows to get AI analysis (`/api/analyze/health`, `/api/analyze/audit`)
- **Knowledge Base**: WiFi best practices, UniFi 10.x features, security guides stored in ChromaDB
- **Live Queries**: Tools to query UniFi APIs for real-time device status

### UniFi Health to Slack
Uses the UniFi Network Integration API with `X-API-KEY`.
- Cron (every 15m) → Get Sites → pick site by `UNIFI_SITE` → fetch devices → analyze health → If degraded → Claude Agent AI analysis → Slack alert

### UniFi Best Practices Audit
Uses the UniFi Local Controller API with cookie-based auth.
- Daily (8 AM) → Authenticate → Fetch (Networks, WLANs, Firewall, Devices) → Analyze → If critical → Claude Agent AI recommendations → Slack alert

## Customization ideas
- Replace HTTP Slack call with the native Slack node using OAuth (reuse the same bot token).
- Add alert throttling with `Move` + `Wait` or a Redis-based rate limiter.
- Add custom knowledge documents to `claude-agent/knowledge/` to enhance AI responses.
- Expose n8n behind HTTPS by putting Traefik/Caddy in front if you'll run it remotely.

## Running locally
- Stop stack: `docker compose down`
- View logs:
  - n8n: `docker compose logs -f n8n`
  - Claude Agent: `docker compose logs -f claude-agent`
  - ChromaDB: `docker compose logs -f chromadb`

## Security
- Set a strong `N8N_ENCRYPTION_KEY` before first launch; changing it later invalidates saved credentials.
- If running on the internet, place n8n behind auth (reverse proxy + basic auth/OIDC) and use HTTPS.
