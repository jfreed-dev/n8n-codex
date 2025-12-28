# Architecture Diagrams

Visual documentation of the n8n-codex stack architecture.

## Table of Contents

1. [Service Topology](#service-topology)
2. [Data Flow - Health Monitoring](#data-flow---health-monitoring)
3. [Data Flow - Security Audit](#data-flow---security-audit)
4. [Claude Agent Internal Architecture](#claude-agent-internal-architecture)
5. [Slack Interaction Flow](#slack-interaction-flow)
6. [Authentication Flows](#authentication-flows)

---

## Service Topology

Network topology showing all services, ports, and connections.

```mermaid
graph TB
    subgraph External["External Services"]
        UNIFI["UniFi Controller<br/>Self-hosted"]
        SLACK["Slack API<br/>slack.com"]
        ANTHROPIC["Anthropic API<br/>api.anthropic.com"]
    end

    subgraph Docker["Docker Network: backend"]
        subgraph N8N["n8n Container"]
            N8N_APP["n8n Workflow Engine<br/>:5678"]
        end

        subgraph PG["PostgreSQL Container"]
            POSTGRES["PostgreSQL 14<br/>:5432"]
        end

        subgraph AGENT["Claude Agent Container"]
            FASTAPI["FastAPI Server<br/>:8080"]
            SLACK_HANDLER["Slack Socket Mode<br/>Handler"]
        end

        subgraph CHROMA["ChromaDB Container"]
            CHROMADB["ChromaDB<br/>:8000"]
        end
    end

    subgraph Volumes["Persistent Storage"]
        PG_VOL[("postgres_data")]
        N8N_VOL[(".n8n_data/")]
        CHROMA_VOL[("chromadb_data/")]
    end

    %% Service Dependencies
    N8N_APP -->|depends_on| POSTGRES
    FASTAPI -->|depends_on| CHROMADB

    %% Volume Mounts
    POSTGRES -.->|mount| PG_VOL
    N8N_APP -.->|mount| N8N_VOL
    CHROMADB -.->|mount| CHROMA_VOL

    %% Internal Connections
    N8N_APP -->|HTTP :8080| FASTAPI
    FASTAPI -->|HTTP :8000| CHROMADB
    N8N_APP -->|PostgreSQL :5432| POSTGRES

    %% External Connections
    N8N_APP -->|HTTPS| UNIFI
    N8N_APP -->|HTTPS| SLACK
    FASTAPI -->|HTTPS| UNIFI
    FASTAPI -->|HTTPS| ANTHROPIC
    SLACK_HANDLER <-->|WebSocket| SLACK

    classDef external fill:#f9f,stroke:#333,stroke-width:2px
    classDef container fill:#bbf,stroke:#333,stroke-width:2px
    classDef volume fill:#bfb,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5

    class UNIFI,SLACK,ANTHROPIC external
    class N8N_APP,POSTGRES,FASTAPI,SLACK_HANDLER,CHROMADB container
    class PG_VOL,N8N_VOL,CHROMA_VOL volume
```

---

## Data Flow - Health Monitoring

Every 15 minutes: monitors device health and alerts on degradation.

```mermaid
sequenceDiagram
    autonumber
    participant SCHED as Schedule Trigger
    participant N8N as n8n Workflow
    participant UNIFI_INT as UniFi Integration API
    participant JS as JavaScript Node
    participant AGENT as Claude Agent
    participant CLAUDE as Claude Sonnet 4
    participant SLACK as Slack API

    SCHED->>N8N: Trigger (every 15 min)

    N8N->>UNIFI_INT: GET /sites
    Note right of UNIFI_INT: X-API-KEY header auth
    UNIFI_INT-->>N8N: Site list

    N8N->>JS: Pick site by UNIFI_SITE env
    JS-->>N8N: Selected site ID

    N8N->>UNIFI_INT: GET /sites/{id}/devices
    UNIFI_INT-->>N8N: Device list with status

    N8N->>JS: Analyze device health
    Note right of JS: Check: offline, adopting,<br/>firmware, CPU/mem, uptime
    JS-->>N8N: Health summary + degraded flag

    alt Degraded = true
        N8N->>AGENT: POST /api/analyze/health
        AGENT->>CLAUDE: Analyze with context

        opt Tool calls needed
            CLAUDE->>AGENT: Tool request
            AGENT->>AGENT: Execute tool
            AGENT->>CLAUDE: Tool result
        end

        CLAUDE-->>AGENT: Analysis text
        AGENT-->>N8N: AI recommendations

        N8N->>SLACK: POST chat.postMessage
        Note right of SLACK: Alert with analysis
        SLACK-->>N8N: Message sent
    else Healthy
        N8N->>N8N: Log healthy status
    end
```

---

## Data Flow - Security Audit

Daily at 8 AM: comprehensive security audit with AI recommendations.

```mermaid
sequenceDiagram
    autonumber
    participant SCHED as Daily Schedule
    participant N8N as n8n Workflow
    participant UNIFI_CTRL as UniFi Controller API
    participant JS as JavaScript Node
    participant AGENT as Claude Agent
    participant CLAUDE as Claude Sonnet 4
    participant SLACK as Slack API

    SCHED->>N8N: Trigger (8 AM daily)

    N8N->>UNIFI_CTRL: POST /api/auth/login
    Note right of UNIFI_CTRL: username/password auth
    UNIFI_CTRL-->>N8N: Set-Cookie session

    N8N->>JS: Extract session cookie
    JS-->>N8N: Cookie for requests

    par Fetch Configuration Data
        N8N->>UNIFI_CTRL: GET /rest/networkconf
        UNIFI_CTRL-->>N8N: Network/VLAN config
    and
        N8N->>UNIFI_CTRL: GET /rest/wlanconf
        UNIFI_CTRL-->>N8N: Wireless config
    and
        N8N->>UNIFI_CTRL: GET /rest/firewallrule
        UNIFI_CTRL-->>N8N: Firewall rules
    and
        N8N->>UNIFI_CTRL: GET /stat/device
        UNIFI_CTRL-->>N8N: Device statistics
    end

    N8N->>JS: Comprehensive audit analysis
    Note right of JS: Score: firmware, VLANs,<br/>WPA3, PMF, firewall,<br/>resources → A-F grade
    JS-->>N8N: Findings + severity

    alt Critical or High findings > 0
        N8N->>AGENT: POST /api/analyze/audit
        AGENT->>CLAUDE: Analyze with findings

        opt Tool calls for context
            CLAUDE->>AGENT: Tool request
            AGENT->>AGENT: Execute tool
            AGENT->>CLAUDE: Tool result
        end

        CLAUDE-->>AGENT: Recommendations
        AGENT-->>N8N: AI audit report

        N8N->>SLACK: POST chat.postMessage
        Note right of SLACK: Critical findings alert
        SLACK-->>N8N: Message sent
    else All checks passed
        N8N->>N8N: Log passed status
    end
```

---

## Claude Agent Internal Architecture

Component structure of the Claude Agent service.

```mermaid
graph TB
    subgraph External["External APIs"]
        ANTHROPIC["Anthropic API<br/>Claude Sonnet 4"]
        UNIFI_INT["UniFi Integration API<br/>X-API-KEY"]
        UNIFI_CTRL["UniFi Controller API<br/>Cookie Auth"]
        SLACK_API["Slack API"]
    end

    subgraph FastAPI["FastAPI Application :8080"]
        MAIN["main.py<br/>Lifespan Manager"]

        subgraph Routes["API Routes"]
            HEALTH["/api/health"]
            READY["/api/ready"]
            QUERY["/api/query"]
            ANALYZE_H["/api/analyze/health"]
            ANALYZE_A["/api/analyze/audit"]
            KB_SEARCH["/api/knowledge/search"]
        end
    end

    subgraph Agent["Agent Core"]
        CORE["UniFiExpertAgent<br/>Agentic Loop (max 10 iter)"]
        TOOLS["Tool Executor<br/>20+ tools defined"]

        subgraph ToolCategories["Tool Categories"]
            READ_TOOLS["Read Tools<br/>(safe operations)"]
            ADMIN_TOOLS["Admin Tools<br/>(require confirmation)"]
        end
    end

    subgraph Knowledge["Knowledge Base"]
        EMBEDDINGS["ChromaDB Client"]
        DOCS["Markdown Docs<br/>wifi, security, troubleshooting"]
    end

    subgraph SlackIntegration["Slack Integration"]
        HANDLER["Socket Mode Handler"]
        CONFIRM["Confirmation System<br/>5-min TTL store"]
        DUO["Duo MFA<br/>(optional)"]
    end

    subgraph UniFiClients["UniFi API Clients"]
        INT_CLIENT["Integration Client"]
        CTRL_CLIENT["Controller Client"]
    end

    CHROMADB[("ChromaDB<br/>:8000")]

    %% Connections
    MAIN --> Routes
    MAIN --> HANDLER
    MAIN --> EMBEDDINGS

    Routes --> CORE
    CORE --> TOOLS
    TOOLS --> ToolCategories

    READ_TOOLS --> UniFiClients
    ADMIN_TOOLS --> CONFIRM
    CONFIRM --> UniFiClients
    CONFIRM -.-> DUO

    EMBEDDINGS --> CHROMADB
    EMBEDDINGS --> DOCS

    HANDLER <--> SLACK_API
    HANDLER --> CORE
    HANDLER --> CONFIRM

    CORE --> ANTHROPIC
    INT_CLIENT --> UNIFI_INT
    CTRL_CLIENT --> UNIFI_CTRL

    classDef external fill:#f9f,stroke:#333
    classDef route fill:#bfb,stroke:#333
    classDef agent fill:#bbf,stroke:#333
    classDef storage fill:#fbb,stroke:#333

    class ANTHROPIC,UNIFI_INT,UNIFI_CTRL,SLACK_API external
    class HEALTH,READY,QUERY,ANALYZE_H,ANALYZE_A,KB_SEARCH route
    class CORE,TOOLS,READ_TOOLS,ADMIN_TOOLS agent
    class CHROMADB,EMBEDDINGS,DOCS storage
```

---

## Slack Interaction Flow

User interaction via Slack with confirmation for admin actions.

```mermaid
sequenceDiagram
    autonumber
    participant USER as Slack User
    participant SLACK as Slack Platform
    participant HANDLER as Socket Mode Handler
    participant AGENT as UniFiExpertAgent
    participant CLAUDE as Claude Sonnet 4
    participant TOOLS as Tool Executor
    participant CONFIRM as Confirmation Store
    participant DUO as Duo MFA (optional)
    participant UNIFI as UniFi APIs

    USER->>SLACK: @mention or DM question
    SLACK->>HANDLER: WebSocket event
    HANDLER->>AGENT: query(message)
    AGENT->>CLAUDE: Process with tools

    alt Read-only query
        CLAUDE->>TOOLS: get_unifi_devices, etc.
        TOOLS->>UNIFI: API request
        UNIFI-->>TOOLS: Data response
        TOOLS-->>CLAUDE: Tool result
        CLAUDE-->>AGENT: Response text
        AGENT-->>HANDLER: Answer
        HANDLER->>SLACK: Post message
        SLACK->>USER: Display answer

    else Admin action requested
        CLAUDE->>TOOLS: device_admin_command
        TOOLS-->>AGENT: ConfirmationRequired
        AGENT-->>HANDLER: Needs confirmation

        HANDLER->>CONFIRM: Store pending action (5-min TTL)
        HANDLER->>SLACK: Block Kit message
        Note right of SLACK: Approve/Deny buttons<br/>Risk level indicator
        SLACK->>USER: Display confirmation UI

        USER->>SLACK: Click Approve
        SLACK->>HANDLER: Button interaction

        opt Duo MFA enabled
            HANDLER->>DUO: Push notification
            DUO-->>HANDLER: Approved
        end

        HANDLER->>CONFIRM: Validate & retrieve action
        HANDLER->>TOOLS: Execute with confirm_token
        TOOLS->>UNIFI: Admin API call
        UNIFI-->>TOOLS: Success
        TOOLS-->>HANDLER: Result
        HANDLER->>SLACK: Success message
        SLACK->>USER: Action completed
    end
```

---

## Authentication Flows

How different components authenticate with external services.

```mermaid
graph LR
    subgraph N8N["n8n Workflows"]
        N8N_HEALTH["Health Workflow"]
        N8N_AUDIT["Audit Workflow"]
        N8N_SLACK["Slack Nodes"]
    end

    subgraph Agent["Claude Agent"]
        AGENT_INT["Integration Client"]
        AGENT_CTRL["Controller Client"]
        AGENT_CLAUDE["Claude API Client"]
        AGENT_SLACK["Slack Handler"]
    end

    subgraph AuthMethods["Authentication Methods"]
        API_KEY["X-API-KEY Header<br/>(UNIFI_API_TOKEN)"]
        COOKIE["Cookie Session<br/>(username/password login)"]
        BEARER["Bearer Token<br/>(SLACK_BOT_TOKEN)"]
        ANTHROPIC_KEY["x-api-key Header<br/>(ANTHROPIC_API_KEY)"]
        SOCKET["App Token + Socket Mode<br/>(SLACK_APP_TOKEN)"]
    end

    subgraph APIs["External APIs"]
        UNIFI_INT_API["UniFi Integration API<br/>/proxy/network/integration/v1/"]
        UNIFI_CTRL_API["UniFi Controller API<br/>/proxy/network/api/s/{site}/"]
        SLACK_API["Slack Web API"]
        SLACK_SOCKET["Slack Socket Mode"]
        CLAUDE_API["Anthropic API"]
    end

    %% n8n auth flows
    N8N_HEALTH -->|uses| API_KEY
    N8N_AUDIT -->|uses| COOKIE
    N8N_SLACK -->|uses| BEARER

    API_KEY --> UNIFI_INT_API
    COOKIE --> UNIFI_CTRL_API
    BEARER --> SLACK_API

    %% Agent auth flows
    AGENT_INT -->|uses| API_KEY
    AGENT_CTRL -->|uses| COOKIE
    AGENT_CLAUDE -->|uses| ANTHROPIC_KEY
    AGENT_SLACK -->|uses| SOCKET

    ANTHROPIC_KEY --> CLAUDE_API
    SOCKET --> SLACK_SOCKET

    classDef workflow fill:#bfb,stroke:#333
    classDef agent fill:#bbf,stroke:#333
    classDef auth fill:#fbf,stroke:#333
    classDef api fill:#fbb,stroke:#333

    class N8N_HEALTH,N8N_AUDIT,N8N_SLACK workflow
    class AGENT_INT,AGENT_CTRL,AGENT_CLAUDE,AGENT_SLACK agent
    class API_KEY,COOKIE,BEARER,ANTHROPIC_KEY,SOCKET auth
    class UNIFI_INT_API,UNIFI_CTRL_API,SLACK_API,SLACK_SOCKET,CLAUDE_API api
```

---

## Component Summary

| Component | Port | Purpose | Dependencies |
|-----------|------|---------|--------------|
| n8n | 5678 | Workflow automation | PostgreSQL |
| PostgreSQL | 5432 | n8n persistence | - |
| Claude Agent | 8080 | AI-powered UniFi expert | ChromaDB |
| ChromaDB | 8000 | Vector knowledge base | - |

## Data Persistence

| Volume | Mount Point | Contains |
|--------|-------------|----------|
| `postgres_data` | /var/lib/postgresql/data | n8n workflows, credentials |
| `.n8n_data/` | /home/node/.n8n | n8n config, logs |
| `chromadb_data/` | /chroma/chroma | Knowledge base vectors |

## Tool Categories

### Read Tools (No Confirmation)
- `get_unifi_sites`, `get_unifi_devices`, `get_device_details`
- `get_network_config`, `get_wlan_config`, `get_firewall_rules`
- `get_connected_clients`, `get_client_details`
- `get_traffic_stats`, `get_dpi_stats`, `get_top_clients`
- `get_recent_events`, `get_alarms`
- `search_knowledge_base`

### Admin Tools (Require Confirmation)
- `device_admin_command` - locate, restart, adopt, upgrade, forget
- `client_admin_command` - kick, block, unblock
- `create_guest_access` - temporary network access
- `update_wlan_settings` - SSID enable/disable, password changes
- `update_firewall_rule_settings` - rule enable/disable
