# n8n-codex Session Notes

## Date: 2025-12-14

## Summary
Configured n8n with two Unifi Network monitoring workflows and resolved activation issues.

---

## Workflows Created

### 1. Unifi Health to Slack (Devices-Based)
- **File**: `workflows/unifi_health_to_slack.json`
- **ID**: `HHPR09dfftrqgV7i`
- **Schedule**: Every 15 minutes
- **Purpose**: Monitor device health, alert on offline/degraded devices
- **API Used**: Unifi Integration API (`/proxy/network/integration/v1/`)
- **Auth**: HTTP Header Auth with X-API-KEY

### 2. Unifi Best Practices Audit
- **File**: `workflows/unifi_best_practices_audit.json`
- **ID**: `CNiJU6ABVBwHvKok`
- **Schedule**: Daily at 8 AM
- **Purpose**: Security audit checking VLANs, WPA3, PMF, firmware, firewall rules
- **API Used**: Unifi Local Controller API (`/proxy/network/api/s/{site}/`)
- **Auth**: Cookie-based session auth (username/password via env vars)

---

## Unifi API Reference

### Two Different APIs

1. **Integration API** (limited, newer)
   - Base: `https://{controller}/proxy/network/integration/v1/`
   - Auth: `X-API-KEY` header
   - Endpoints: `/sites`, `/sites/{id}/devices`
   - No health endpoint available

2. **Local Controller API** (full access)
   - Base: `https://{controller}/proxy/network/api/s/{site}/`
   - Auth: Cookie session from `/api/auth/login`
   - Endpoints:
     - `/stat/health` - System health
     - `/stat/device` - Device stats
     - `/rest/networkconf` - Networks/VLANs
     - `/rest/wlanconf` - Wireless configs
     - `/rest/firewallrule` - Firewall rules

---

## Credentials in n8n

| ID | Name | Type | Used By |
|----|------|------|---------|
| `JGGcHH1qRD1Ov2OS` | Unifi API Key | httpHeaderAuth | Health workflow |
| `811evcI0T3nHShsO` | Slack Bot Token | httpHeaderAuth | Both workflows |

### Credential Configuration
- **Unifi API Key**: Header name `X-API-KEY`, value from Unifi Network Application
- **Slack Bot Token**: Header name `Authorization`, value `Bearer xoxb-...`

---

## Environment Variables

```bash
# Database
POSTGRES_USER=n8n
POSTGRES_PASSWORD=<secure-random-password>
POSTGRES_DB=n8n

# n8n
N8N_ENCRYPTION_KEY=<32-char-secret-set-before-first-launch>

# Unifi - Integration API
UNIFI_BASE_URL=https://<controller-ip>
UNIFI_API_TOKEN=<from Unifi Network Application>
UNIFI_SITE=default

# Unifi - Local Controller API (for audit workflow)
UNIFI_USERNAME=<unifi-username>
UNIFI_PASSWORD=<unifi-password>

# Slack
SLACK_CHANNEL=#alerts
SLACK_BOT_TOKEN=<bot-token>
```

---

## Issues Encountered & Solutions

### 1. Health endpoint 404
**Problem**: `/proxy/network/integration/v1/sites/{id}/health` doesn't exist
**Solution**: Derive health from device state via `/devices` endpoint

### 2. Workflow import missing versionId
**Problem**: n8n 1.x requires `versionId` in workflow JSON
**Solution**: Add UUID versionId to workflow JSON before import

### 3. Credential ID mismatch
**Problem**: Workflow JSON had placeholder credential IDs (`slack-bot-token`, `unifi-api-key`)
**Solution**: Update to actual database IDs via SQL:
```sql
UPDATE workflow_entity
SET nodes = REPLACE(nodes::text, '"id": "slack-bot-token"', '"id": "811evcI0T3nHShsO"')::jsonb
WHERE name = 'Workflow Name';
```

### 4. Workflow activation error (WorkflowHistoryService.getVersion)
**Problem**: Empty `workflow_history` table and missing `activeVersionId`
**Solution**:
```sql
-- Insert history records
INSERT INTO workflow_history ("workflowId", "versionId", authors, connections, nodes, name, "createdAt", "updatedAt")
SELECT id, "versionId", 'claude', connections, nodes, name, NOW(), NOW()
FROM workflow_entity WHERE name LIKE 'Unifi%';

-- Set activeVersionId
UPDATE workflow_entity SET "activeVersionId" = "versionId" WHERE name LIKE 'Unifi%';
```

### 5. Multiple Slack alerts from parallel branches
**Problem**: Parallel workflow branches each triggered analysis node
**Solution**: Changed to sequential execution flow

---

## Useful Commands

```bash
# Start/stop stack
docker compose up -d
docker compose down

# View logs
docker compose logs -f n8n

# List workflows
docker compose exec -T n8n n8n list:workflow

# Database access
docker compose exec -T postgres psql -U n8n -d n8n

# Check workflow status
docker compose exec -T postgres psql -U n8n -d n8n -c \
  "SELECT name, active FROM workflow_entity;"

# Check credentials
docker compose exec -T postgres psql -U n8n -d n8n -c \
  "SELECT id, name, type FROM credentials_entity;"

# Restart n8n after DB changes
docker compose restart n8n
```

---

## Database Schema Notes

Key tables:
- `workflow_entity` - Workflow definitions
- `workflow_history` - Version history (required for activation)
- `credentials_entity` - Encrypted credentials

Important columns in `workflow_entity`:
- `id` - Workflow ID (used in CLI)
- `versionId` - Current version UUID
- `activeVersionId` - Must reference `workflow_history.versionId`
- `active` - Boolean activation status
- `nodes` - JSONB of node definitions (contains credential IDs)

---

## WLAN Security Findings (from /tmp/wlans.json)

Networks found with security issues:
- All WLANs using WPA2 (not WPA3)
- PMF (802.11w) disabled on all networks
- Passwords visible in API response (audit workflow checks these)

---

## Best Practices Review (2025-12-14)

### Changes Made
1. **Redacted credentials** - Removed hardcoded secrets from this file
2. **Improved .gitignore** - Added editor files, OS files, backup patterns
3. **Added Docker healthchecks** - Both n8n and PostgreSQL now have healthchecks
4. **Updated depends_on** - n8n waits for healthy postgres before starting

### Remaining Recommendations
- **N8N_ENCRYPTION_KEY**: Still set to placeholder in `.env` - generate a proper 32-char secret
- **OpenAI Codex workflow**: Uses deprecated `/v1/completions` endpoint and `code-davinci-002` model (deprecated by OpenAI). Consider updating to `/v1/chat/completions` with `gpt-4` or `gpt-3.5-turbo`
- **Credential rotation**: Consider rotating Unifi and Slack credentials since they may have been exposed in earlier commit history

### n8n Version
- Running version: 1.123.5 (latest as of review date)

---

## Claude Agent Implementation (2025-12-14)

### Overview
Replaced OpenAI Codex with a Claude-powered intelligent agent service that:
- Acts as UniFi network expert (WiFi, networking, security, UniFi 10.x)
- Answers questions via Slack (Socket Mode - works behind firewall)
- Provides AI analysis for existing n8n workflows
- Uses ChromaDB for RAG-based knowledge retrieval

### New Services Added

| Service | Port | Purpose |
|---------|------|---------|
| `claude-agent` | 8080 | Claude AI agent with UniFi expertise |
| `chromadb` | 8000 | Vector database for knowledge base |

### Claude Agent Directory Structure

```
claude-agent/
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── main.py              # FastAPI + Slack startup
│   ├── config.py            # Environment configuration
│   ├── agent/
│   │   ├── core.py          # Claude API client with tool use
│   │   ├── tools.py         # UniFi tool definitions
│   │   └── prompts.py       # System prompts
│   ├── slack/
│   │   └── handler.py       # Slack Socket Mode handler
│   ├── api/
│   │   └── routes.py        # HTTP API for n8n
│   ├── knowledge/
│   │   └── embeddings.py    # ChromaDB client
│   └── unifi/
│       ├── integration_api.py   # X-API-KEY auth
│       └── controller_api.py    # Cookie session auth
└── knowledge/               # Markdown docs indexed to ChromaDB
    ├── unifi_10x_features.md
    ├── wifi_best_practices.md
    ├── network_security.md
    ├── troubleshooting.md
    └── faqs.md
```

### HTTP API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/query` | POST | General agent query |
| `/api/analyze/health` | POST | Analyze device health (for Health workflow) |
| `/api/analyze/audit` | POST | Generate recommendations (for Audit workflow) |
| `/api/knowledge/search` | POST | Search knowledge base |

### Available Tools (MCP-style)

The agent has these tools available:
- `get_unifi_sites` - List all UniFi sites
- `get_unifi_devices` - Get device status and firmware
- `get_device_details` - Detailed info for specific device
- `get_network_config` - VLAN/network configuration
- `get_wlan_config` - Wireless settings (WPA3, PMF)
- `get_firewall_rules` - Firewall rule list
- `search_knowledge_base` - RAG search of documentation

### Workflow Updates

Both workflows now call the Claude agent for AI-powered analysis:

**Unifi Health to Slack**:
- Added "AI Analysis" node after "If Degraded"
- Calls `/api/analyze/health` with device data
- Slack alert includes AI analysis

**Unifi Best Practices Audit**:
- Added "AI Recommendations" node after "Analyze"
- Calls `/api/analyze/audit` with findings and raw config
- Slack alert includes AI remediation recommendations

### New Environment Variables

```bash
# Anthropic (required)
ANTHROPIC_API_KEY=sk-ant-...

# Slack Socket Mode (required for Slack integration)
SLACK_APP_TOKEN=xapp-...
```

### Slack App Configuration

To enable Socket Mode:
1. Go to https://api.slack.com/apps > Your App
2. Enable **Socket Mode** in settings
3. Generate App-Level Token with `connections:write` scope
4. Add to `.env` as `SLACK_APP_TOKEN`
5. Subscribe to events: `app_mention`, `message.im`
6. Add bot scopes: `chat:write`, `app_mentions:read`, `im:history`

### Starting the New Services

```bash
# Build and start all services
docker compose up -d --build

# View claude-agent logs
docker compose logs -f claude-agent

# Check ChromaDB health
curl http://localhost:8000/api/v1/heartbeat

# Test agent health
curl http://localhost:8080/api/health

# Test a query
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are best practices for VLAN segmentation?"}'
```

### Token Optimization Strategy

- Workflows collect data via direct API calls (no AI tokens)
- AI analysis only triggered when issues detected
- Knowledge base cached in ChromaDB (no re-embedding)
- Uses Claude Sonnet for balance of capability and cost

---

## Next Steps / TODO

- [x] ~~Update OpenAI workflow to use chat completions API~~ (Replaced with Claude Agent)
- [ ] Generate proper N8N_ENCRYPTION_KEY (warning: changing invalidates credentials)
- [ ] Add ANTHROPIC_API_KEY to `.env`
- [ ] Configure Slack Socket Mode (generate xapp- token)
- [ ] Build and test claude-agent service
- [ ] Configure WPA3 on wireless networks
- [ ] Enable PMF (Protected Management Frames)
- [ ] Set up firewall rules for VLAN isolation
- [ ] Create IoT-specific network if not exists
- [ ] Review and rotate credentials (may have been exposed in git history)
