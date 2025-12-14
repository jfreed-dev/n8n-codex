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

## Next Steps / TODO

- [ ] Generate proper N8N_ENCRYPTION_KEY (warning: changing invalidates credentials)
- [ ] Update OpenAI workflow to use chat completions API
- [ ] Configure WPA3 on wireless networks
- [ ] Enable PMF (Protected Management Frames)
- [ ] Set up firewall rules for VLAN isolation
- [ ] Create IoT-specific network if not exists
- [ ] Review and rotate credentials (may have been exposed in git history)
