# Contoso PoC - Task Tracking

## Project: Talk to Your Data Logs with Azure AI
**Status**: Operational (all core components working)
**Created**: 2026-03-20

---

## Phase 1: Infrastructure Setup
| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Update `infra/variables.sh` with actual subscription ID | ✅ Done | 439cf6ec-8907-40ee-bae2-7efd9656cd09 |
| 1.2 | Run `az login` and verify subscription | ✅ Done | |
| 1.3 | Execute `infra/deploy.sh` to create all Azure resources | ✅ Done | 7 scripts (01-07) |
| 1.4 | Verify Elasticsearch VM is running | ✅ Done | http://20.212.115.93:9200 |
| 1.5 | Verify Kibana UI is accessible | ✅ Done | http://20.212.115.93:5601, 11 panel dashboard |
| 1.6 | Verify Zabbix VM is running | ✅ Done | http://52.230.33.83/zabbix (Admin/zabbix) |
| 1.7 | Verify E-Commerce VM is running | ✅ Done | http://4.194.60.39/ |
| 1.8 | Verify Streamlit VM is running | ✅ Done | http://4.193.143.174:8501 |
| 1.9 | Test E-Commerce: browse, add to cart, checkout | ✅ Done | Logs visible in ES |
| 1.10 | Verify AI Search index created | ✅ Done | logs-index, 1618 docs, semantic + vector |
| 1.11 | Verify AI Foundry model deployments | ✅ Done | gpt-4o + text-embedding-ada-002 |
| 1.12 | Configure managed identity on Streamlit VM | ✅ Done | Cognitive Services OpenAI User role |
| 1.13 | Add NSG AllowAllInbound rule | ✅ Done | Priority 200 (may need re-add after Azure ops) |

## Phase 2: Ingestion Pipeline
| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Set environment variables (.env on VM) | ✅ Done | /opt/tcc/.env on Streamlit VM |
| 2.2 | Install Python dependencies | ✅ Done | venv at /opt/tcc/venv |
| 2.3 | Generate sample logs | ✅ Done | 1618 docs in ES |
| 2.4 | Bulk load sample data into Elasticsearch | ✅ Done | infrastructure-logs index |
| 2.5 | Bulk sync ES → AI Search | ✅ Done | 1618 docs synced with embeddings |
| 2.6 | Verify data in AI Search index | ✅ Done | All 1618 docs indexed |
| 2.7 | Add semantic config to AI Search index | ✅ Done | my-semantic-config |
| 2.8 | Configure Logstash on ES VM | ✅ Done | HTTP input :5044 → ES |
| 2.9 | (Optional) Function App ingestion | ⚠️ Issue | Container restart loop — bypassed with bulk sync |

## Phase 3: Backend (MCP Server)
| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Install dependencies | ✅ Done | mcp 1.26.0, openai, azure-search-documents |
| 3.2 | Configure backend config (DefaultAzureCredential) | ✅ Done | No API key used for OpenAI |
| 3.3 | Start MCP server as systemd service | ✅ Done | mcp-server.service on port 8080 |
| 3.4 | Test: `search_infrastructure_logs` | ✅ Done | Semantic + vector search, 200 OK |
| 3.5 | Test: `get_recent_alerts` | ✅ Done | 84 alerts returned, 200 OK |
| 3.6 | Test: `analyze_log_data` | ✅ Done | GPT-4o analysis working |
| 3.7 | Test: `get_ecommerce_transactions` | ✅ Done | 2706 transactions, 200 OK |
| 3.8 | Test: `get_system_health_summary` | ✅ Done | Combined analysis working |

## Phase 4: Frontend (Streamlit)
| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Install dependencies | ✅ Done | streamlit 1.55.0, httpx 0.28.1 |
| 4.2 | Configure frontend (DefaultAzureCredential + MCP headers) | ✅ Done | Accept header fix applied |
| 4.3 | Launch Streamlit as systemd service | ✅ Done | streamlit.service on port 8501 |
| 4.4 | Fix MCP Streamable HTTP 406 error | ✅ Done | Added Accept: application/json, text/event-stream |
| 4.5 | Test: Natural language queries | ✅ Done | All 5 tools callable via chat |
| 4.6 | Test: E-Commerce quick actions | ✅ Done | Orders, payments, products |
| 4.7 | Test: Sidebar filters | ✅ Done | Severity, hostname, service |

## Phase 5: Code Audit & Documentation
| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | Audit all backend code | ✅ Done | All 7 files correct |
| 5.2 | Audit frontend code | ✅ Done | Removed unused AZURE_OPENAI_KEY imports |
| 5.3 | Audit ingestion code | ✅ Done | Fixed: DefaultAzureCredential for OpenAI |
| 5.4 | Audit infra scripts | ✅ Done | 7 scripts, all consistent |
| 5.5 | Fix .env / .env.example | ✅ Done | Corrected endpoint, cleared API key |
| 5.6 | Update README.md | ✅ Done | 4 VMs, auth, architecture, known issues |
| 5.7 | Update ARCHITECTURE.md | ✅ Done | DefaultAzureCredential, Streamlit VM, bulk sync |
| 5.8 | Update TASKS.md | ✅ Done | This file |

## Phase 6: Demo Preparation
| # | Task | Status | Notes |
|---|------|--------|-------|
| 6.1 | Prepare demo script / talking points | ⬜ TODO | |
| 6.2 | Demo: E-Commerce purchase flow end-to-end | ⬜ TODO | Browse → Buy → Log → AI Query |
| 6.3 | Demo: Payment failure investigation via chat | ⬜ TODO | "Why are payments failing?" |
| 6.4 | Capture screenshots for documentation | ⬜ TODO | |

## Phase 7: Cleanup
| # | Task | Status | Notes |
|---|------|--------|-------|
| 7.1 | Delete Azure resource group | ⬜ TODO | `az group delete --name rg-tcc-poc` |
| 7.2 | Remove local SSH keys if generated | ⬜ TODO | |
| 7.3 | Document lessons learned | ⬜ TODO | |

---

## Key Decisions & Lessons Learned

### Decisions Made
1. **Authentication**: `DefaultAzureCredential` (managed identity) — subscription enforces `disableLocalAuth=true` on Cognitive Services
2. **Ingestion**: Bulk sync on Streamlit VM (Python script) — Function App has container restart issue
3. **AI Model**: GPT-4o (eastus, GlobalStandard) + text-embedding-ada-002 for vectors
4. **Search**: Azure AI Search with semantic config (`my-semantic-config`) + vector search (HNSW, cosine, 1536 dims)
5. **Backend protocol**: MCP Streamable HTTP — requires `Accept: application/json, text/event-stream` header
6. **Frontend**: Streamlit with httpx for MCP JSON-RPC calls
7. **VM count**: 4 VMs (ES+Kibana, Zabbix, E-Commerce, Streamlit+MCP)

### Issues Encountered & Resolved
| Issue | Root Cause | Resolution |
|-------|-----------|------------|
| OpenAI 401 errors | `disableLocalAuth=true` policy blocks API keys | Switched to `DefaultAzureCredential` everywhere |
| MCP 406 Not Acceptable | Missing `Accept` header on httpx requests | Added `Accept: application/json, text/event-stream` to all requests |
| Semantic search failures | No semantic config on AI Search index | Added `my-semantic-config` via PUT API |
| Function App restart loop | Container Oryx build succeeds but app won't start | Bypassed with bulk sync on Streamlit VM |
| NSG rules disappearing | Unknown Azure behavior after certain operations | Re-added `AllowAllInbound` rule (priority 200) |
| ES client version mismatch | elasticsearch-py v9 incompatible | Pinned to `>=8.12.0,<9.0.0` |

### Known Issues
1. **Function App**: `func-tcc-poc-ingestion` container restart loop (low priority)
2. **NSG**: `AllowAllInbound` rule may need re-adding after Azure management operations
3. **Cost**: 4 VMs running continuously (~$350-380/month) — stop VMs when not demoing
