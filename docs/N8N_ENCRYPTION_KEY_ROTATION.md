# N8N_ENCRYPTION_KEY Rotation Plan

## Overview

The `N8N_ENCRYPTION_KEY` is used by n8n to encrypt sensitive data such as credentials. The current `.env` file has a placeholder value that should be replaced with a cryptographically secure key.

**WARNING**: Changing this key will invalidate ALL existing credentials stored in n8n. They cannot be decrypted with a new key and must be re-created.

---

## Current State

```bash
# Current placeholder in .env
N8N_ENCRYPTION_KEY=generate-a-32-char-secret
```

This placeholder provides no real security and should be replaced.

---

## Pre-Rotation Checklist

### 1. Document Existing Credentials

Before rotating, document all credentials that will need to be re-created:

| Credential Name | Type | Used By | Notes |
|-----------------|------|---------|-------|
| Unifi API Key | httpHeaderAuth | Health workflow | `X-API-KEY` header |
| Slack Bot Token | httpHeaderAuth | Both workflows | `Authorization: Bearer` |

**To list credentials:**
```bash
docker compose exec -T postgres psql -U n8n -d n8n -c \
  "SELECT id, name, type FROM credentials_entity;"
```

### 2. Gather Credential Values

Ensure you have access to the raw credential values:

| Credential | Source |
|------------|--------|
| `UNIFI_API_TOKEN` | UniFi Network Application → Settings → API |
| `SLACK_BOT_TOKEN` | Slack API → Your App → OAuth & Permissions |

These values are already in `.env` and can be referenced when re-creating credentials.

### 3. Backup Current State

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Export workflow definitions (these are NOT encrypted)
docker compose exec -T postgres pg_dump -U n8n -d n8n \
  --table=workflow_entity \
  --data-only > backups/$(date +%Y%m%d)/workflows.sql

# Export credential metadata (encrypted data will be useless after rotation)
docker compose exec -T postgres psql -U n8n -d n8n -c \
  "SELECT id, name, type FROM credentials_entity;" \
  > backups/$(date +%Y%m%d)/credentials_list.txt

# Full database backup (optional, for rollback)
docker compose exec -T postgres pg_dump -U n8n -d n8n \
  > backups/$(date +%Y%m%d)/full_backup.sql
```

---

## Rotation Steps

### Step 1: Stop n8n

```bash
docker compose stop n8n
```

### Step 2: Generate New Encryption Key

Generate a cryptographically secure 32+ character key:

```bash
# Option A: Using openssl (recommended)
openssl rand -hex 16
# Output example: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6

# Option B: Using /dev/urandom
head -c 32 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32

# Option C: Using Python
python3 -c "import secrets; print(secrets.token_hex(16))"
```

### Step 3: Update .env File

```bash
# Edit .env and replace the placeholder
# OLD: N8N_ENCRYPTION_KEY=generate-a-32-char-secret
# NEW: N8N_ENCRYPTION_KEY=<your-generated-key>
```

### Step 4: Clear Invalid Credentials

The old encrypted credentials cannot be decrypted. Remove them:

```bash
docker compose exec -T postgres psql -U n8n -d n8n -c \
  "DELETE FROM credentials_entity;"
```

### Step 5: Start n8n

```bash
docker compose up -d n8n
```

### Step 6: Re-Create Credentials via n8n UI

1. Open n8n at http://localhost:5678
2. Go to **Settings** → **Credentials**
3. Create each credential:

**Unifi API Key:**
- Name: `Unifi API Key`
- Type: Header Auth
- Header Name: `X-API-KEY`
- Header Value: (copy from `UNIFI_API_TOKEN` in `.env`)

**Slack Bot Token:**
- Name: `Slack Bot Token`
- Type: Header Auth
- Header Name: `Authorization`
- Header Value: `Bearer <SLACK_BOT_TOKEN from .env>`

### Step 7: Update Workflow Credential References

After creating new credentials, their IDs will be different. Update workflows:

```bash
# Get new credential IDs
docker compose exec -T postgres psql -U n8n -d n8n -c \
  "SELECT id, name FROM credentials_entity;"
```

Then update each workflow to use the new credential IDs:
- Open each workflow in the n8n UI
- Edit nodes that use credentials
- Re-select the credential from the dropdown
- Save the workflow

### Step 8: Test Workflows

```bash
# Manually trigger health workflow
# In n8n UI: Open workflow → Click "Execute Workflow"

# Check logs for errors
docker compose logs -f n8n
```

---

## Rollback Plan

If something goes wrong:

```bash
# Stop n8n
docker compose stop n8n

# Restore old encryption key in .env
# N8N_ENCRYPTION_KEY=generate-a-32-char-secret

# Restore database from backup (if needed)
docker compose exec -T postgres psql -U n8n -d n8n < backups/YYYYMMDD/full_backup.sql

# Restart n8n
docker compose up -d n8n
```

**Note:** Rollback only works if you haven't deleted the old credentials and are restoring to the exact previous state.

---

## Post-Rotation Verification

| Check | Command/Action | Expected Result |
|-------|----------------|-----------------|
| n8n healthy | `curl http://localhost:5678/healthz` | `{"status":"ok"}` |
| Credentials exist | n8n UI → Settings → Credentials | Both credentials listed |
| Health workflow | Execute manually | Completes without auth errors |
| Audit workflow | Execute manually | Completes without auth errors |
| Slack alerts | Trigger test alert | Message appears in #alerts |

---

## Security Recommendations

1. **Never commit the encryption key** - Keep it only in `.env` (already in `.gitignore`)
2. **Store backup securely** - The key should be stored in a password manager or secrets vault
3. **Document the key location** - Note where the key is stored for disaster recovery
4. **Consider secrets management** - For production, use Docker secrets or HashiCorp Vault

---

## Estimated Downtime

| Phase | Duration |
|-------|----------|
| Preparation (backup, documentation) | 10-15 min |
| n8n downtime (stop → credential recreation) | 5-10 min |
| Workflow testing | 5-10 min |
| **Total** | **20-35 min** |

---

## Execution Checklist

- [ ] Document existing credentials
- [ ] Verify access to raw credential values
- [ ] Create database backup
- [ ] Stop n8n
- [ ] Generate new encryption key
- [ ] Update `.env` file
- [ ] Clear old credentials from database
- [ ] Start n8n
- [ ] Re-create credentials in UI
- [ ] Update workflow credential references
- [ ] Test health workflow
- [ ] Test audit workflow
- [ ] Verify Slack alerts working
- [ ] Store new key securely
- [ ] Update SESSION_NOTES.md
