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

## Testing Results (2025-12-14)

### Service Status
| Service | Status | Port |
|---------|--------|------|
| n8n | healthy | 5678 |
| postgres | healthy | 5432 |
| chromadb | healthy | 8000 |
| claude-agent | healthy | 8080 |

### API Endpoint Tests
| Endpoint | Method | Result |
|----------|--------|--------|
| `/api/health` | GET | ✅ `{"status":"healthy"}` |
| `/api/knowledge/stats` | GET | ✅ 117 documents indexed |
| `/api/knowledge/search` | POST | ✅ RAG search working |
| `/api/query` | POST | ✅ Claude API responding |
| `/api/analyze/health` | POST | ✅ Returns AI analysis with recommendations |
| `/api/analyze/audit` | POST | ✅ Returns prioritized remediation steps |

### Slack Bot Test
- Socket Mode: ✅ Connected (session established)
- DM Response: ✅ Working
- Tool Execution: ✅ `search_knowledge_base` called successfully
- Response Time: ~15 seconds (includes knowledge base search)

### n8n Workflow Integration
| Workflow | Schedule | AI Trigger Condition | Status |
|----------|----------|---------------------|--------|
| Unifi Health to Slack | Every 15 min | When devices degraded | ✅ Running |
| Unifi Best Practices Audit | Daily 8 AM | When critical/high issues | ✅ Running |

**Note:** AI endpoints only called when issues detected (saves tokens). Recent executions show all devices healthy with no critical findings.

### Fixes Applied During Testing
1. **requirements.txt**: Changed `claude-code-sdk` → `anthropic` (uses direct API)
2. **docker-compose.yml**: Updated chromadb healthcheck to use bash tcp check (curl not in container)

---

## OpenAI Codex Cleanup (2025-12-14)

### Changes Made
Removed all OpenAI Codex references from the codebase:

| File | Action |
|------|--------|
| `workflows/openai_codex_inference.json` | Deleted |
| `README.md` | Updated title, description, prereqs |
| `CLAUDE.md` | Removed Codex workflow section |
| `AGENTS.md` | Updated project structure, testing guidelines |
| `GEMINI.md` | Updated to reflect Claude Agent |
| `.env.example` | Removed `OPENAI_API_KEY`, `OPENAI_MODEL` |
| `docker-compose.yml` | Removed OpenAI env vars from n8n service |

### Commits
- `ce611b8` - Update README to reflect Claude Agent replacing OpenAI Codex
- `01cdb7b` - Remove OpenAI Codex references, replace with Claude Agent

---

## Post-Cleanup Testing (2025-12-14)

### Stack Restart Verification
All services started successfully after configuration changes:

| Service | Status | Health Check |
|---------|--------|--------------|
| postgres | healthy | `pg_isready` ✅ |
| chromadb | healthy | TCP 8000 ✅ |
| n8n | healthy | `/healthz` → `{"status":"ok"}` |
| claude-agent | healthy | `/api/health` → `{"status":"healthy"}` |

### Claude Agent Endpoint Tests

| Endpoint | Test | Result |
|----------|------|--------|
| `GET /api/health` | Health check | ✅ `{"status":"healthy"}` |
| `POST /api/query` | "Best practices for securing UniFi network" | ✅ Returned detailed WPA3/firewall recommendations with live network data |
| `POST /api/analyze/health` | Mock device data with degraded status | ✅ AI identified UDM-Pro high CPU, U6-Pro restart, provided remediation |
| `POST /api/analyze/audit` | Mock audit findings | ✅ Prioritized recommendations (Critical → Medium) with specific UniFi paths |
| `POST /api/knowledge/search` | "WPA3 security best practices" | ✅ 5 results from knowledge base (69% top relevance) |
| `GET /api/knowledge/stats` | Knowledge base status | ✅ 117 documents indexed in `unifi_knowledge` collection |

### Slack Integration Test

| Component | Status |
|-----------|--------|
| Socket Mode | ⚡️ Connected (session `s_15736413143901`) |
| Bot Auth | ✅ `n8n_codex` @ `freeddev.slack.com` |
| Message Send | ✅ Test message posted to `#alerts` |

### Live UniFi API Calls (via Agent)
During query tests, the agent successfully called:
- `get_unifi_devices` → Fetched from Integration API
- `get_wlan_config` → Retrieved WLAN settings
- `get_network_config` → Retrieved VLAN configuration
- `get_firewall_rules` → Retrieved firewall rules
- `search_knowledge_base` → ChromaDB vector search

All API calls authenticated and returned data from the live UniFi controller.

---

## Administrative Tools & Confirmation Flow (2025-12-16)

### Overview
Extended the Claude-powered Slack bot with:
- Additional read capabilities (clients, traffic, events, alarms)
- Administrative write capabilities with safety controls
- Confirmation-based approval flow with Slack interactive buttons
- Duo MFA integration for dangerous/critical actions

### New Read Tools Added

| Tool | Description |
|------|-------------|
| `get_connected_clients` | List clients with MAC, IP, hostname, signal, traffic |
| `get_client_details` | Full details for a specific client by MAC |
| `get_traffic_stats` | Bandwidth usage trends over time |
| `get_dpi_stats` | Application-level traffic breakdown (DPI) |
| `get_top_clients` | Top bandwidth consumers |
| `get_recent_events` | Device and client events |
| `get_alarms` | Active network alarms |

### Administrative Tools Added

| Tool | Risk Level | Confirmation |
|------|------------|--------------|
| `device_admin_command` (locate) | Safe | None |
| `device_admin_command` (restart) | Moderate | Slack button |
| `device_admin_command` (upgrade/forget) | Dangerous/Critical | Slack + Duo MFA |
| `client_admin_command` (unblock) | Safe | None |
| `client_admin_command` (kick) | Moderate | Slack button |
| `client_admin_command` (block) | Dangerous | Slack + Duo MFA |
| `create_guest_access` | Safe | None |
| `update_wlan_settings` | Varies | Depends on operation |
| `update_firewall_rule_settings` | Dangerous | Slack + Duo MFA |

### Confirmation Flow Architecture

```
User Request → Agent Decides Action → Risk Assessment
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    ▼                      ▼                      ▼
                  Safe               Moderate              Dangerous/Critical
                    │                      │                      │
            Execute Now         Slack Approve/Deny      Slack Approve/Deny
                                          │                      │
                                   On Approve            On Approve
                                          │                      │
                                   Execute Now            Duo MFA Push
                                                               │
                                                        On Approve
                                                               │
                                                        Execute Now
```

### New Files Created

| File | Purpose |
|------|---------|
| `claude-agent/src/agent/confirmations.py` | Confirmation store, Duo MFA client, pending action management |

### Files Modified

| File | Changes |
|------|---------|
| `controller_api.py` | Added read methods (clients, events, alarms, DPI) and write methods (device/client commands, WLAN/firewall updates) |
| `tools.py` | Added 12+ new tools with ConfirmationRequired dataclass |
| `handler.py` | Added Slack interactive button handlers for Approve/Deny flow |
| `core.py` | Handle ConfirmationRequired responses from tools |
| `prompts.py` | Updated system prompt with new tool documentation |
| `config.py` | Added Duo environment variables |
| `requirements.txt` | Added `duo_client>=5.0.0` |
| `docker-compose.yml` | Added Duo env vars to claude-agent service |

### New Environment Variables

```bash
# Duo MFA (for admin action confirmations)
DUO_INTEGRATION_KEY=...
DUO_SECRET_KEY=...
DUO_API_HOST=api-XXXXXXXX.duosecurity.com
DUO_MFA_USER=user@example.com
```

### UniFi API 403 Forbidden Fix

**Problem**: All write operations (POST/PUT/DELETE) to UniFi API returned 403 Forbidden, while read operations worked fine.

**Root Cause**: UniFi OS (Dream Machine products) requires a CSRF token for all write operations. The token is returned in the `x-csrf-token` response header after authentication.

**Solution** (in `controller_api.py`):
1. Capture `x-csrf-token` from authentication response
2. Include it in all write operation headers
3. Re-authenticate on 403 responses (CSRF token expiry)

```python
# Key changes in controller_api.py
self._csrf_token: str | None = None

# In authenticate():
self._csrf_token = response.headers.get("x-csrf-token")

# In _request():
if method.upper() in ("POST", "PUT", "DELETE") and self._csrf_token:
    headers["x-csrf-token"] = self._csrf_token
```

### Testing Results

| Command | Flow | Result |
|---------|------|--------|
| "Locate device aa:bb:cc:dd:ee:01" | Safe → Execute | ✅ HTTP 200 |
| "Restart device aa:bb:cc:dd:ee:02" | Moderate → Confirm → Execute | ✅ HTTP 200 |
| "Block client aa:bb:cc:dd:ee:03" | Dangerous → Confirm → Duo MFA → Execute | ✅ HTTP 200 |
| "Unblock client aa:bb:cc:dd:ee:03" | Safe → Execute | ✅ HTTP 200 |

### Commits

- `e66c631` - Fix UniFi API 403 Forbidden on write operations (CSRF token fix)

---

## Next Steps / TODO

- [x] ~~Update OpenAI workflow to use chat completions API~~ (Replaced with Claude Agent)
- [x] ~~Add ANTHROPIC_API_KEY to `.env`~~
- [x] ~~Configure Slack Socket Mode (generate xapp- token)~~
- [x] ~~Build and test claude-agent service~~
- [x] ~~Remove OpenAI Codex references from codebase~~
- [x] ~~Verify stack restart after cleanup~~
- [x] ~~Add administrative tools with confirmation flow~~
- [x] ~~Integrate Duo MFA for dangerous actions~~
- [x] ~~Fix UniFi API 403 Forbidden (CSRF token)~~
- [ ] Generate proper N8N_ENCRYPTION_KEY (warning: changing invalidates credentials)
- [ ] Configure WPA3 on wireless networks
- [ ] Enable PMF (Protected Management Frames)
- [ ] Set up firewall rules for VLAN isolation
- [ ] Create IoT-specific network if not exists
- [ ] Review and rotate credentials (may have been exposed in git history)
