# Contoso PoC - Talk to Your Data Logs with Azure AI

## Overview

This Proof of Concept demonstrates a hybrid cloud architecture where:
- **On-premises simulation (4 VMs in Azure, southeastasia region)**:
  - **E-Commerce VM** — Simple web shop (Nginx + Flask/Gunicorn) generating transaction logs
  - **Zabbix VM** — Infrastructure monitoring with web dashboard
  - **Elasticsearch VM** — Centralized log storage with **Kibana** web UI and **Logstash** ingestion
  - **Streamlit VM** — AI chatbot frontend (Streamlit) + MCP Server backend
- **Azure Cloud Services**: AI Foundry (GPT-4o + Embeddings) + AI Search enable natural language querying of all operational logs

**Key Demo**: A customer browses the Contoso Shop, adds items to cart, checks out → All events are logged to Elasticsearch → Viewable in Kibana → Synced to Azure AI Search with vector embeddings → Queryable via natural language ("Show me failed payment orders today")

## Authentication

> **IMPORTANT**: The Azure subscription enforces `disableLocalAuth=true` on Cognitive Services.
> All code uses **`DefaultAzureCredential`** (Azure managed identity on VMs, `az login` for local dev).
> API keys for Azure OpenAI are **not used** — the `AZURE_OPENAI_KEY` field in `.env` is left empty.
> AI Search still uses admin key authentication (local auth is supported for AI Search).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│           ON-PREMISES SIMULATION (4 VMs in southeastasia)               │
│                                                                         │
│  ┌──────────────────┐                                                   │
│  │  E-Commerce VM   │   Nginx (port 80) → Flask/Gunicorn (port 5000)   │
│  │ ecommerce-web-01 │──┐ Purchase/cart/page logs                        │
│  └──────────────────┘  │                                                │
│                        │                                                │
│  ┌──────────────────┐  │  ┌─────────────────────────────────────┐      │
│  │   Zabbix VM      │──┼─>│  Elasticsearch VM                    │      │
│  │   Dashboard:     │  │  │  ES API:  http://<es-ip>:9200       │      │
│  │   http://<ip>/   │  │  │  Kibana:  http://<es-ip>:5601      │      │
│  │   zabbix         │──┘  │  Logstash (:5044, HTTP input)       │      │
│  │  (Admin/zabbix)  │     └──────────────┬──────────────────────┘      │
│  └──────────────────┘                    │                              │
│                                          │  Bulk sync (Python)          │
│  ┌────────────────────────────────────┐  │  + vector embeddings         │
│  │  Streamlit VM                      │  │                              │
│  │  MCP Server (:8080, 5 tools)      │<─┘                              │
│  │  Streamlit UI (:8501, chatbot)    │                                  │
│  │  DefaultAzureCredential (MI)      │                                  │
│  └────────────────────────────────────┘                                 │
│                                                                         │
└──────────────────────────────────────────┼──────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           AZURE CLOUD                                   │
│                                                                         │
│  ┌────────────────────┐     ┌─────────────────────┐                    │
│  │  Azure AI Search   │<────│  Bulk Sync Service   │                    │
│  │  (Semantic + Vec)  │     │  (Python on          │                    │
│  │  logs-index        │     │   Streamlit VM)      │                    │
│  │  1618 docs         │     └─────────────────────┘                    │
│  └────────┬───────────┘                                                │
│           │                                                             │
│           ▼                                                             │
│  ┌────────────────────┐     ┌─────────────────────┐                    │
│  │  Azure AI Foundry  │<────│  MCP Server          │                    │
│  │  (GPT-4o + Embed)  │     │  (5 Tools, port 8080)│                    │
│  │  DefaultAzureCred  │     │  Streamable HTTP     │                    │
│  └────────────────────┘     └──────────┬──────────┘                    │
│                                        │                                │
│                              ┌─────────▼──────────┐                    │
│                              │  Streamlit Frontend │                    │
│                              │  (Chat + E-Commerce │                    │
│                              │   Quick Actions)    │                    │
│                              └─────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| E-Commerce | Nginx + Flask/Gunicorn (VM) | Simple web shop generating purchase/cart/payment logs |
| Monitoring | Zabbix 6.4 (VM) | Infrastructure metrics, alerts, web dashboard |
| Log Store | Elasticsearch 8.x (VM) | Centralized log storage and indexing |
| Log UI | Kibana (on ES VM, port 5601) | Visual Elasticsearch dashboard for log exploration |
| Ingestion | Logstash (HTTP input → ES) + Bulk Sync (ES → AI Search with embeddings) | Real-time log pipeline |
| Search Index | Azure AI Search (semantic + vector) | Indexed logs with semantic config `my-semantic-config` |
| AI Model | Azure AI Foundry (GPT-4o + text-embedding-ada-002) | NLU, analysis, and vector embeddings |
| Backend | MCP Server (Python, 5 tools, Streamable HTTP) | Orchestrates AI Search queries + AI Foundry analysis |
| Frontend | Streamlit (port 8501) | Chat interface for "talk to your logs" |

## VM Setup (all in southeastasia region)

| VM | Azure Name | Purpose | Access |
|----|------------|---------|--------|
| Elasticsearch + Kibana | `vm-elasticsearch` | Centralized logs + Kibana UI | ES: `http://<ip>:9200` / Kibana: `http://<ip>:5601` |
| Zabbix | `vm-zabbix` | Monitoring server + web dashboard | `http://<ip>/zabbix` (Admin / zabbix) |
| E-Commerce | `vm-ecommerce` | Nginx + Flask web shop | `http://<ip>/` (browse & buy) |
| Streamlit + MCP | `vm-streamlit` | AI chatbot + MCP backend | Streamlit: `http://<ip>:8501` / MCP: `http://<ip>:8080` |

> All VMs: Standard_B2ms, Ubuntu 22.04, SSH key auth, user `tccadmin`

## What You Can See

### 1. Zabbix Dashboard → `http://<zabbix-vm-ip>/zabbix`
- **Login**: Admin / zabbix
- Monitor CPU, memory, disk, network across all VMs
- View alerts, event history, and trigger status

### 2. Kibana (Elasticsearch UI) → `http://<es-vm-ip>:5601`
- Explore all logs in the `infrastructure-logs` index (1618+ docs)
- Use **Discover** to browse raw log entries (infra + ecommerce)
- Pre-built dashboard with 11 visualizations

### 3. E-Commerce Shop → `http://<ecommerce-vm-ip>/`
- Browse product catalog (8 products: electronics, accessories, furniture)
- Add items to cart, enter name, checkout
- ~90% payment success rate (10% simulate failures for demo)
- Every action generates logs → Elasticsearch → Kibana

### 4. Streamlit AI Chat → `http://<streamlit-vm-ip>:8501`
- Natural language queries: "Show me all failed payment orders today"
- Infrastructure queries: "Which servers have high CPU usage?"
- Quick action buttons for infrastructure + e-commerce queries
- Powered by Azure AI Foundry (GPT-4o) + Azure AI Search

## MCP Server Tools

The backend exposes 5 tools via the Model Context Protocol (MCP) Streamable HTTP transport:

| Tool | Description | Data Source |
|------|-------------|-------------|
| `search_infrastructure_logs` | Semantic + vector search over all indexed logs | Azure AI Search |
| `analyze_log_data` | GPT-4o powered analysis of log patterns | Azure AI Foundry |
| `get_recent_alerts` | Query Zabbix monitoring alerts | Elasticsearch (direct) |
| `get_ecommerce_transactions` | Query e-commerce purchase/cart/payment logs | Elasticsearch (direct) |
| `get_system_health_summary` | AI-generated health report (infra + e-commerce) | Combined |

## Ingestion Pipeline

### E-Commerce → Elasticsearch
```
Contoso Shop (Flask) → HTTP POST → Logstash (:5044) → Elasticsearch (infrastructure-logs)
```

### Elasticsearch → Azure AI Search
**Bulk Sync (Primary)**: Python script on Streamlit VM polls all ES docs, generates vector embeddings via Azure OpenAI (text-embedding-ada-002), and pushes to Azure AI Search with `mergeOrUpload`.

**Continuous Sync (Alternative)**: `ingestion/sync_es_to_ai_search.py` polls every 30s for incremental updates.

> **Note**: An Azure Function App (`func-tcc-poc-ingestion`) was also deployed but has a container restart loop. The bulk sync approach on the Streamlit VM is the working solution.

## Quick Start

```bash
# 1. Deploy Azure infrastructure (4 VMs + AI services)
cd infra
chmod +x deploy.sh
./deploy.sh

# 2. Wait ~5 min for cloud-init, then access:
#    - Zabbix:      http://<zabbix-ip>/zabbix      (Admin / zabbix)
#    - Kibana:      http://<es-ip>:5601             (explore logs)
#    - E-Commerce:  http://<ecommerce-ip>/          (browse & buy)
#    - Streamlit:   http://<streamlit-ip>:8501      (AI chatbot)
#    - MCP Server:  http://<streamlit-ip>:8080      (backend API)

# 3. (Optional) Run bulk sync to push all ES data to AI Search
ssh tccadmin@<streamlit-ip>
cd /opt/tcc
source venv/bin/activate
python ingestion/bulk_sync.py

# 4. (Optional) Run local development
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
# Ensure az login and managed identity / RBAC is configured
python backend/mcp_server.py &
streamlit run frontend/app.py
```

## Prerequisites

- Azure CLI installed and authenticated (`az login`)
- Python 3.10+
- Azure subscription with:
  - Azure AI Foundry (GPT-4o + text-embedding-ada-002 deployments)
  - Azure AI Search (Basic tier)
  - 4x Azure Virtual Machines (Standard_B2ms)
- **Managed Identity**: Streamlit VM must have a system-assigned managed identity with `Cognitive Services OpenAI User` role on the AI Foundry resource
- Region: **southeastasia** (VMs + AI Search), **eastus** (AI Foundry - GPT-4o GlobalStandard)

## Folder Structure

```
PoC/
├── README.md                    # This file
├── ARCHITECTURE.md              # Detailed architecture document
├── TASKS.md                     # Task tracking
├── .env.example                 # Environment variables template
├── .env                         # Actual environment variables (gitignored)
├── infra/                       # Azure CLI deployment scripts
│   ├── deploy.sh                # Main deployment (runs all scripts)
│   ├── destroy.sh               # Tear down all resources
│   ├── variables.sh             # Environment variables / naming
│   ├── 01-resource-group.sh     # Resource group creation
│   ├── 02-network.sh            # VNet, subnets, NSGs
│   ├── 03-onprem-vms.sh         # ES+Kibana, Zabbix, E-Commerce VMs
│   ├── 04-ai-search.sh          # Azure AI Search + index + semantic config
│   ├── 05-ai-foundry.sh         # AI Foundry (GPT-4o + Embeddings)
│   ├── 06-function-app.sh       # Ingestion Function App (has restart issue)
│   └── 07-streamlit-vm.sh       # Streamlit + MCP Server VM
├── ecommerce-app/               # E-Commerce web application
│   ├── app.py                   # Flask app (products, cart, checkout)
│   ├── requirements.txt         # Flask dependencies
│   ├── nginx-ecommerce.conf     # Nginx reverse proxy config
│   └── ecommerce.service        # systemd service unit file
├── ingestion/                   # Elasticsearch → AI Search sync
│   ├── sync_es_to_ai_search.py  # Continuous sync (30s polling)
│   ├── logstash.conf            # Logstash config (HTTP input → ES)
│   ├── config.py                # Configuration
│   └── requirements.txt         # Dependencies (incl. azure-identity)
├── backend/                     # MCP Server (5 tools)
│   ├── mcp_server.py            # FastMCP server (Streamable HTTP)
│   ├── config.py                # Configuration
│   ├── requirements.txt         # Dependencies
│   └── tools/
│       ├── search_logs.py       # AI Search (semantic + vector)
│       ├── analyze_logs.py      # AI Foundry GPT-4o analysis
│       ├── zabbix_alerts.py     # Zabbix alert query (ES direct)
│       └── ecommerce_logs.py    # E-Commerce transaction query (ES direct)
├── frontend/                    # Streamlit UI
│   ├── app.py                   # Streamlit chat app + MCP client
│   ├── config.py                # Configuration
│   └── requirements.txt         # Dependencies
└── sample-data/                 # Sample log data for testing
    ├── sample_logs.json         # Infrastructure + e-commerce sample logs
    └── generate_logs.py         # Log generator (infra + ecommerce entries)
```

## Estimated Cost (~$330-380/month)

| Resource | Cost |
|----------|------|
| 4x VMs (Standard_B2ms) | ~$240 |
| Azure AI Search (Basic) | ~$70 |
| Azure OpenAI (GPT-4o + Embeddings) | ~$20-40 |
| Function App + Storage | ~$1-5 |

## Known Issues

1. **Function App container restart loop**: `func-tcc-poc-ingestion` deploys successfully but enters a start/stop loop. Bypassed by running bulk sync directly on the Streamlit VM.
2. **NSG rules**: The `AllowAllInbound` rule on `nsg-onprem` has been observed disappearing. May need to re-add after certain Azure operations.

## Cleanup

```bash
az group delete --name rg-tcc-poc --yes --no-wait
```
