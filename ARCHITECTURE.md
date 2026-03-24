# Contoso PoC - Architecture Document

## 1. Executive Summary

This PoC demonstrates how Contoso can leverage Azure AI services to enable **natural language querying of infrastructure and e-commerce operational logs**. The solution bridges on-premises infrastructure (Zabbix monitoring + Elasticsearch + an e-commerce web app on Nginx) with Azure cloud AI capabilities (AI Foundry + AI Search), allowing operations teams to "talk to their logs" through a conversational AI interface.

**Key scenario**: A simple e-commerce web shop runs on an on-prem server behind Nginx. Every purchase, cart action, and page view generates logs sent to Elasticsearch. These logs (along with Zabbix monitoring data) are synced to Azure AI Search and queryable via natural language.

**Authentication**: All Azure OpenAI calls use **`DefaultAzureCredential`** (managed identity on VMs). The subscription policy enforces `disableLocalAuth=true` on Cognitive Services — API keys cannot be used for OpenAI endpoints.

## 2. Current State (On-Premises Simulation — 4 VMs)

### 2.1 E-Commerce Web Application (NEW)
- **Role**: Simple online shop ("Contoso Shop") serving product catalog, cart, and checkout
- **Stack**: Nginx (reverse proxy) → Flask/Gunicorn (Python web app)
- **Hostname**: `ecommerce-web-01`
- **Generates logs for**: Page views, add-to-cart events, checkout/purchase transactions, payment successes/failures
- **All logs** → sent directly to Elasticsearch via the app

### 2.2 Zabbix Monitoring
- **Role**: Infrastructure monitoring and alerting
- **Monitors**: CPU, memory, disk, network, service health across all on-prem servers (including the e-commerce VM)
- **Outputs**: Alerts, metrics, and event data → forwarded to Elasticsearch

### 2.3 Elasticsearch
- **Role**: Centralized log storage and basic search
- **Ingests**: Zabbix alerts, system logs (syslog), application logs, **e-commerce transaction logs**
- **Index**: `infrastructure-logs` with structured fields including ecommerce sub-document
- **Kibana**: Web UI on port 5601 for visual log exploration, dashboards, and Discover
- **Current limitation**: Kibana requires manual dashboard setup; no natural language interface (that's what the AI layer solves)

## 3. Target Architecture (Azure AI Layer)

### 3.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│              ON-PREMISES SIMULATION (4 VMs)                          │
│                                                                      │
│  ┌────────────┐                                                      │
│  │   Zabbix   │─── monitors ──┐                                     │
│  │  Server    │               │                                     │
│  │  :80/zabbix│               │                                     │
│  └────────────┘               ▼                                     │
│                          ┌────────────┐                              │
│  ┌────────────────────┐  │  Logstash  │    ┌─────────────────┐      │
│  │  E-Commerce Web    │─>│  (:5044)   │───>│  Elasticsearch   │      │
│  │  (Nginx + Flask)   │  │  HTTP input│    │   (Port 9200)    │      │
│  │  Contoso Shop      │  └────────────┘    │  Kibana (:5601)  │      │
│  │  ecommerce-web-01  │                    │  All logs here   │      │
│  └────────────────────┘                    └────────┬─────────┘      │
│                                                     │                │
│  ┌────────────────────────────────────────┐         │                │
│  │  Streamlit VM (vm-streamlit)           │         │                │
│  │  MCP Server (:8080, Streamable HTTP)  │<────────┘                │
│  │  Streamlit UI (:8501, chatbot)        │                          │
│  │  DefaultAzureCredential (managed ID)  │                          │
│  └────────────────────┬──────────────────┘                          │
│                       │                                              │
└───────────────────────┼──────────────────────────────────────────────┘
                        │ DefaultAzureCredential
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          AZURE CLOUD                                 │
│                                                                      │
│  ┌───────────────────┐    ┌──────────────────┐                      │
│  │  Azure AI Search   │<───│  Bulk Sync Svc   │                      │
│  │  (Indexed + Vec)   │    │  (on Streamlit   │                      │
│  │  my-semantic-config│    │   VM, Python)    │                      │
│  └───────┬───────────┘    └──────────────────┘                      │
│          │                                                           │
│  ┌───────▼───────────┐    ┌──────────────────┐                      │
│  │   MCP Server       │───>│ Azure AI Foundry │                      │
│  │   (5 tools)        │    │ (GPT-4o + Embed) │                      │
│  │   Streamable HTTP  │    │ DefaultAzureCred │                      │
│  └───────┬───────────┘    └──────────────────┘                      │
│          │                                                           │
│  ┌───────▼───────────┐                                              │
│  │  Streamlit UI      │                                              │
│  │  (Chat + E-com)    │                                              │
│  └───────────────────┘                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Azure AI Search
- **Purpose**: Indexed, searchable store for infrastructure + e-commerce logs
- **Features used**:
  - **Semantic search**: Natural language understanding of log queries
  - **Vector search**: Embeddings (text-embedding-ada-002) for similarity matching
  - **Facets/Filters**: Severity, hostname, service, category, ecommerce_action, ecommerce_customer
- **Index schema**: Infrastructure fields + ecommerce fields (action, order_id, customer, product, total, status) + vector embedding

### 3.3 Azure AI Foundry (GPT-4o)
- **Purpose**: Natural language understanding and intelligent log analysis
- **Authentication**: `DefaultAzureCredential` (managed identity on VMs, `az login` locally). API keys are disabled by subscription policy (`disableLocalAuth=true`).
- **Endpoint**: `https://ai-tcc-poc.openai.azure.com/` (custom subdomain)
- **Deployed models**:
  - `gpt-4o` (2024-08-06): Chat completions for analysis and Q&A
  - `text-embedding-ada-002`: Vector embeddings for semantic search (1536 dimensions)
- **Region**: eastus (GPT-4o GlobalStandard not available in southeastasia)

### 3.4 MCP Server (Backend)
- **Purpose**: Orchestration layer exposing AI-powered tools
- **Protocol**: Model Context Protocol (MCP) via **Streamable HTTP** transport
- **Location**: Runs on the Streamlit VM (`vm-streamlit`, port 8080)
- **MCP Client**: Frontend uses `httpx` with required `Accept: application/json, text/event-stream` header and JSON-RPC over SSE
- **Tools exposed**:
  | Tool | Description |
  |------|-------------|
  | `search_infrastructure_logs` | Semantic + vector search over all indexed logs |
  | `analyze_log_data` | GPT-4o powered analysis of log patterns |
  | `get_recent_alerts` | Query Zabbix alerts from Elasticsearch |
  | `get_ecommerce_transactions` | Query e-commerce purchase/cart/payment logs |
  | `get_system_health_summary` | AI-generated health report (infra + e-commerce) |

### 3.5 Streamlit Frontend
- **Purpose**: Conversational chat interface for operations teams
- **Location**: Runs on the Streamlit VM (`vm-streamlit`, port 8501)
- **Authentication**: Uses `DefaultAzureCredential` via `get_bearer_token_provider` for Azure OpenAI calls
- **Features**:
  - Natural language chat input
  - Infrastructure quick actions (critical alerts, health summary, CPU)
  - **E-commerce quick actions** (recent orders, payment failures, top products)
  - Sidebar filters (severity, hostname, service)
  - Tool call visibility (shows which MCP tools are invoked)

## 4. Data Flow

### 4.1 E-Commerce Log Flow
```
User browses Contoso Shop → Nginx (port 80)
       │
       ▼
Flask/Gunicorn (port 5000)
       │
       ├── Page view    → send_log("INFO", ..., category="ecommerce")
       ├── Add to cart  → send_log("INFO", ..., ecommerce={action, product, price})
       └── Checkout     → send_log("INFO/ERROR", ..., ecommerce={order_id, total, payment_status})
       │
       ▼  HTTP POST
Logstash (port 5044 on ES VM, HTTP input)
       │
       ▼  Elasticsearch output
Elasticsearch (infrastructure-logs index)
       │
       ▼  Timer trigger (every 5 min)
Azure Function App (vectorization)
       │  Generates embeddings via Azure OpenAI
       ▼
Azure AI Search (logs-index with vector embeddings)
```

### 4.2 Ingestion Pipeline (Elasticsearch → AI Search)

**Bulk Sync (Primary — on Streamlit VM)**
1. Runs as a one-time or periodic script on the Streamlit VM
2. Fetches all documents from Elasticsearch `infrastructure-logs` index
3. Generates vector embeddings for each document via Azure OpenAI (text-embedding-ada-002) using `DefaultAzureCredential`
4. Pushes enriched documents (with `content_vector`) to Azure AI Search
5. Uses `mergeOrUpload` action for idempotent upserts
6. Successfully synced 1618 documents

**Continuous Sync (Alternative — `ingestion/sync_es_to_ai_search.py`)**
- Polls Elasticsearch every 30 seconds for incremental updates
- Same embedding + upload logic as bulk sync
- Uses `DefaultAzureCredential` for Azure OpenAI

**Azure Function App (Deployed but has issues)**
- `func-tcc-poc-ingestion`: Timer-triggered function (every 5 min)
- Successfully deploys via Oryx build but enters a container restart loop
- Bypassed by using the bulk sync approach on the Streamlit VM

**Logstash (E-Commerce → Elasticsearch)**
- HTTP input on port 5044 receives JSON logs from the E-Commerce Flask app
- Forwards to Elasticsearch `infrastructure-logs` index

### 4.3 Query Pipeline (User → AI → Results)

```
User types: "Show me all failed payment orders today"
       │
       ▼
Streamlit Frontend
       │
       ▼
Azure OpenAI (GPT-4o) ─── decides to call get_ecommerce_transactions
       │
       ▼
MCP Server ──┬── search_infrastructure_logs ── Azure AI Search
             ├── analyze_log_data ──────────── Azure AI Foundry
             ├── get_recent_alerts ──────────── Elasticsearch
             ├── get_ecommerce_transactions ─── Elasticsearch (ecommerce)
             └── get_system_health_summary ─── Combined analysis
       │
       ▼
Results synthesized by GPT-4o
       │
       ▼
Displayed in Streamlit chat
```

## 5. Real-time Ingestion: The Challenge & Solution

### 5.1 The Challenge
Azure AI Search does not have a native connector to pull from on-premises Elasticsearch. Data must be **pushed** to AI Search with vector embeddings.

### 5.2 Solution: Bulk Sync + Continuous Polling

The PoC uses a **Python bulk sync script** running on the Streamlit VM that:
1. Fetches all documents from Elasticsearch
2. Generates vector embeddings via Azure OpenAI (text-embedding-ada-002) using `DefaultAzureCredential`
3. Transforms documents to AI Search flat schema (flattening nested ecommerce/metrics fields)
4. Uploads enriched documents to Azure AI Search via `mergeOrUpload`

For continuous updates, `ingestion/sync_es_to_ai_search.py` polls every 30s.

| Component | Role |
|-----------|------|
| **Logstash** (on ES VM, port 5044) | Receives logs from E-Commerce app → forwards to Elasticsearch |
| **Bulk Sync** (on Streamlit VM) | Fetches all ES docs → generates embeddings → pushes to AI Search |
| **Continuous Sync** (optional) | Polls ES every 30s for incremental updates |

### 5.3 Future Enhancement
For production, consider:
- **Azure Event Hubs**: Elasticsearch → Event Hub → Function App → AI Search
- **Filebeat + Kafka**: Filebeat on ES VM → Kafka/Event Hub → Stream processor → AI Search
- **Elasticsearch Watcher**: Trigger webhook on new docs → Azure Function → AI Search

## 6. E-Commerce Application Details

### 6.1 Contoso Shop Features
| Feature | Endpoint | Log Generated |
|---------|----------|---------------|
| Browse products | `GET /` | Page view log |
| Add to cart | `POST /add-to-cart` | Cart action log (product, price) |
| Checkout | `POST /checkout` | Order log (order_id, total, payment_status) |
| Health check | `GET /health` | Health check log |
| API | `GET /api/products` | API access log |

### 6.2 E-Commerce Log Schema
```json
{
  "timestamp": "2026-03-20T10:30:00Z",
  "hostname": "ecommerce-web-01",
  "severity": "INFO",
  "service": "nginx",
  "message": "POST /checkout - Order ORD-847291 by Ahmad: 2 items, total $51.98 - PAYMENT SUCCESS",
  "source": "ecommerce-app",
  "category": "ecommerce",
  "ecommerce": {
    "action": "checkout",
    "status": "success",
    "order_id": "ORD-847291",
    "customer": "Ahmad",
    "total": 51.98,
    "item_count": 2,
    "payment_status": "success"
  },
  "metrics": { "cpu_percent": 42.0, "memory_percent": 55.0, ... }
}
```

### 6.3 Payment Simulation
- **90% success rate** (configurable)
- Failed payments generate ERROR severity logs with "gateway_timeout"
- Useful for demonstrating AI root cause analysis

## 7. Security Considerations

- **Authentication**: `DefaultAzureCredential` for all Azure OpenAI calls (subscription enforces `disableLocalAuth=true`)
- **Managed Identity**: Streamlit VM has system-assigned managed identity with `Cognitive Services OpenAI User` role
- VM SSH keys (no password auth)
- NSG rules: `AllowAllInbound` + `AllowAllOutbound` on `nsg-onprem` (PoC only — not for production)
- E-commerce app bound to localhost (127.0.0.1:5000), only accessible via Nginx reverse proxy
- AI Search admin keys stored in environment variables (use Key Vault in production)
- Azure OpenAI API keys are **not used** — cleared from `.env` files

## 8. Azure Resources Summary

| Resource | SKU | Estimated Cost/Month |
|----------|-----|---------------------|
| Resource Group (rg-tcc-poc) | - | Free |
| VNet + Subnets | - | Free |
| VM - Elasticsearch (B2ms) | Standard_B2ms | ~$60 |
| VM - Elasticsearch: Kibana | (included) | ~$0 |
| VM - Zabbix (B2ms) | Standard_B2ms | ~$60 |
| VM - E-Commerce (B2ms) | Standard_B2ms | ~$60 |
| VM - Streamlit + MCP (B2ms) | Standard_B2ms | ~$60 |
| Azure AI Search | Basic | ~$70 |
| Azure OpenAI (GPT-4o) | GlobalStandard (10 TPM) | ~$15-30 |
| Azure OpenAI (Embeddings) | GlobalStandard (10 TPM) | ~$5-10 |
| Function App (B1 plan) | Basic | ~$13 |
| Storage Account | Standard LRS | ~$1 |
| **Total Estimated** | | **~$350-380/month** |

## 9. Cleanup

```bash
# Delete all PoC resources
az group delete --name rg-tcc-poc --yes --no-wait
```
