#!/bin/bash
# =============================================================================
# TCC PoC - Main Deployment Script
# Deploys all Azure resources for the TCC Talk-to-Your-Logs PoC
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

echo "============================================================"
echo "  TCC PoC - Full Infrastructure Deployment"
echo "  Talk to Your Data Logs with Azure AI"
echo "============================================================"
echo ""

# Verify Azure CLI is installed and logged in
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI is not installed. Please install it first."
    exit 1
fi

az account show > /dev/null 2>&1 || {
    echo "❌ Not logged in to Azure. Please run 'az login' first."
    exit 1
}

echo "Current Azure account:"
az account show --query "{Subscription:name, ID:id, Tenant:tenantId}" -o table
echo ""
read -p "Continue with this subscription? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "[1/7] Creating Resource Group..."
bash "$SCRIPT_DIR/01-resource-group.sh"
echo ""

echo "[2/7] Setting up Networking..."
bash "$SCRIPT_DIR/02-network.sh"
echo ""

echo "[3/7] Creating On-Prem Simulation VMs (Elasticsearch, Zabbix, E-Commerce)..."
bash "$SCRIPT_DIR/03-onprem-vms.sh"
echo ""

echo "[4/7] Deploying Azure AI Search..."
bash "$SCRIPT_DIR/04-ai-search.sh"
echo ""

echo "[5/7] Deploying Azure AI Foundry..."
bash "$SCRIPT_DIR/05-ai-foundry.sh"
echo ""

echo "[6/7] Creating Ingestion Function App..."
bash "$SCRIPT_DIR/06-function-app.sh"
echo ""

echo "[7/7] Creating Streamlit VM (MCP Server + Chatbot)..."
bash "$SCRIPT_DIR/07-streamlit-vm.sh"
echo ""

ES_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ELASTICSEARCH" -d --query publicIps -o tsv 2>/dev/null || echo '<es-ip>')
ZABBIX_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ZABBIX" -d --query publicIps -o tsv 2>/dev/null || echo '<zabbix-ip>')
ECOMMERCE_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ECOMMERCE" -d --query publicIps -o tsv 2>/dev/null || echo '<ecommerce-ip>')
STREAMLIT_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_STREAMLIT" -d --query publicIps -o tsv 2>/dev/null || echo '<streamlit-ip>')

ES_PRIVATE_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ELASTICSEARCH" -d --query privateIps -o tsv 2>/dev/null || echo '<es-private-ip>')
ZABBIX_PRIVATE_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ZABBIX" -d --query privateIps -o tsv 2>/dev/null || echo '<zabbix-private-ip>')
ECOMMERCE_PRIVATE_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ECOMMERCE" -d --query privateIps -o tsv 2>/dev/null || echo '<ecommerce-private-ip>')

AI_ENDPOINT=$(az cognitiveservices account show -g "$RESOURCE_GROUP" -n "$AI_FOUNDRY_NAME" --query "properties.endpoint" -o tsv 2>/dev/null || echo '<ai-endpoint>')
SEARCH_ENDPOINT="https://$AI_SEARCH_NAME.search.windows.net"
FUNC_URL="https://$FUNCTION_APP_NAME.azurewebsites.net"

echo "============================================================"
echo "  ✅ Deployment Complete!"
echo "============================================================"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT SUMMARY"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "─── VM: Elasticsearch + Kibana + Logstash ────────────────"
echo "  Public IP:          $ES_IP"
echo "  Private IP:         $ES_PRIVATE_IP"
echo "  SSH:                ssh tccadmin@$ES_IP  (key-based auth)"
echo "  Elasticsearch:      http://$ES_IP:9200  (no auth)"
echo "  Kibana:             http://$ES_IP:5601  (no auth)"
echo "  Logstash HTTP:      http://$ES_PRIVATE_IP:5044  (internal)"
echo ""
echo "─── VM: Zabbix Monitoring Server ─────────────────────────"
echo "  Public IP:          $ZABBIX_IP"
echo "  Private IP:         $ZABBIX_PRIVATE_IP"
echo "  SSH:                ssh tccadmin@$ZABBIX_IP  (key-based auth)"
echo "  Zabbix Web UI:      http://$ZABBIX_IP/zabbix"
echo "  Zabbix Login:       Admin / zabbix"
echo "  MySQL User:         zabbix / zabbix_poc_pass"
echo "  MySQL Auth Plugin:  mysql_native_password"
echo ""
echo "─── VM: E-Commerce Web App (TCC Shop) ────────────────────"
echo "  Public IP:          $ECOMMERCE_IP"
echo "  Private IP:         $ECOMMERCE_PRIVATE_IP"
echo "  SSH:                ssh tccadmin@$ECOMMERCE_IP  (key-based auth)"
echo "  TCC Shop:           http://$ECOMMERCE_IP  (Nginx → Gunicorn:5000)"
echo "  Health Check:       http://$ECOMMERCE_IP/health"
echo "  Logs sent to:       Logstash → Elasticsearch"
echo "  Zabbix Agent:       Active (reports to $ZABBIX_PRIVATE_IP)"
echo ""
echo "─── VM: Streamlit + MCP Server (AI Chatbot) ──────────────"
echo "  Public IP:          $STREAMLIT_IP"
echo "  SSH:                ssh tccadmin@$STREAMLIT_IP  (key-based auth)"
echo "  Streamlit UI:       http://$STREAMLIT_IP:8501"
echo "  MCP Server:         http://$STREAMLIT_IP:8080  (backend)"
echo ""
echo "─── Azure AI Search ──────────────────────────────────────"
echo "  Endpoint:           $SEARCH_ENDPOINT"
echo "  Index:              $AI_SEARCH_INDEX"
echo "  SKU:                $AI_SEARCH_SKU"
echo ""
echo "─── Azure AI Foundry (OpenAI) ────────────────────────────"
echo "  Endpoint:           $AI_ENDPOINT"
echo "  Location:           $AI_FOUNDRY_LOCATION"
echo "  Chat Model:         gpt-4o (2024-08-06)"
echo "  Embedding Model:    text-embedding-ada-002"
echo ""
echo "─── Azure Function App (ES → AI Search Vectorization) ────"
echo "  URL:                $FUNC_URL"
echo "  Timer:              Every 5 minutes"
echo "  Flow:               ES → Vectorize (OpenAI) → AI Search"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DATA FLOW"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  E-Commerce App  ──HTTP POST──►  Logstash (:5044)"
echo "       │                              │"
echo "       │                              ▼"
echo "  Zabbix monitors ◄────────  Elasticsearch (:9200)"
echo "                                      │"
echo "                              Azure Function (5 min)"
echo "                                      │"
echo "                                      ▼"
echo "                              AI Search (vectors)"
echo "                                      │"
echo "                              MCP Server (:8080)"
echo "                                      │"
echo "                              Streamlit Chatbot"
echo ""
echo "─── Next Steps ─────────────────────────────────────────────"
echo "  1. Browse TCC Shop:      http://$ECOMMERCE_IP"
echo "  2. Open Streamlit Chat:  http://$STREAMLIT_IP:8501"
echo "  3. Check Kibana:         http://$ES_IP:5601"
echo "  4. Check Zabbix:         http://$ZABBIX_IP/zabbix"
echo ""
echo "─── Teardown ───────────────────────────────────────────────"
echo "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
echo ""
