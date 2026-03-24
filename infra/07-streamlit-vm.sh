#!/bin/bash
# =============================================================================
# TCC PoC - 07 - Streamlit VM (MCP Server + Streamlit Frontend)
#
# Creates a dedicated VM for the AI chatbot interface:
#   - MCP Server backend (port 8080)
#   - Streamlit frontend (port 8501)
#
# ─── Access ──────────────────────────────────────────────────────────────────
#  SSH:              ssh tccadmin@<streamlit-ip>  (key-based auth)
#  Streamlit UI:     http://<streamlit-ip>:8501
#  MCP Server:       http://<streamlit-ip>:8080  (internal)
# ─────────────────────────────────────────────────────────────────────────────
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

# ─── Helpers (reused from 03-onprem-vms.sh) ──────────────────────────────────
wait_for_vm_agent() {
  local vm_name="$1"
  echo "  Waiting for $vm_name agent to be ready..."
  for i in $(seq 1 30); do
    STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$vm_name" \
      --query "instanceView.vmAgent.statuses[0].code" -o tsv 2>/dev/null || echo "")
    if [[ "$STATE" == "ProvisioningState/succeeded" ]]; then
      echo "  $vm_name agent ready"
      return 0
    fi
    sleep 10
  done
  echo "  WARNING: $vm_name agent not ready after 5 min, continuing anyway"
}

create_vm_if_not_exists() {
  local vm_name="$1"
  local cloud_init_file="$2"
  if az vm show -g "$RESOURCE_GROUP" -n "$vm_name" --query name -o tsv 2>/dev/null; then
    echo "  ⏭️  VM '$vm_name' already exists, skipping creation"
  else
    az vm create \
      --resource-group "$RESOURCE_GROUP" \
      --name "$vm_name" \
      --image "$VM_IMAGE" \
      --size "$VM_SIZE" \
      --vnet-name "$VNET_NAME" \
      --subnet "$SUBNET_ONPREM" \
      --admin-username "$ADMIN_USERNAME" \
      --generate-ssh-keys \
      --public-ip-sku Standard \
      --nsg "" \
      --custom-data "$cloud_init_file" \
      --tags $TAGS
    echo "  ✅ VM '$vm_name' created"
  fi
}

# ─── Create VM ────────────────────────────────────────────────────────────────
echo "=========================================="
echo "Creating Streamlit VM: $VM_STREAMLIT"
echo "=========================================="

cat > /tmp/cloud-init-streamlit.yaml << 'CLOUDINIT'
#cloud-config
package_update: true
packages:
  - python3-pip
  - python3-venv
CLOUDINIT

create_vm_if_not_exists "$VM_STREAMLIT" /tmp/cloud-init-streamlit.yaml

echo "✅ Streamlit VM created"

# ─── Enable managed identity ─────────────────────────────────────────────────
echo "  Enabling managed identity on Streamlit VM..."
VM_PRINCIPAL_ID=$(az vm identity assign \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_STREAMLIT" \
  --query systemAssignedIdentity -o tsv 2>/dev/null || \
  az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_STREAMLIT" \
    --query identity.principalId -o tsv)
echo "  Streamlit VM principal: $VM_PRINCIPAL_ID"

# Assign Cognitive Services OpenAI User role
AI_FOUNDRY_ID=$(az cognitiveservices account show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --query id -o tsv 2>/dev/null || echo "")

if [[ -n "$AI_FOUNDRY_ID" ]]; then
  az role assignment create \
    --assignee "$VM_PRINCIPAL_ID" \
    --role "Cognitive Services OpenAI User" \
    --scope "$AI_FOUNDRY_ID" \
    2>/dev/null || echo "  (role assignment may already exist)"
  echo "✅ Managed identity + OpenAI role assigned to Streamlit VM"
else
  echo "⚠️  AI Foundry not found, skipping role assignment"
fi

# ─── Wait for cloud-init ─────────────────────────────────────────────────────
wait_for_vm_agent "$VM_STREAMLIT"
echo "Waiting 30s for cloud-init package installs..."
sleep 30

# ─── Gather credentials ──────────────────────────────────────────────────────
ES_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ELASTICSEARCH" -d --query publicIps -o tsv 2>/dev/null || echo "")

AI_ENDPOINT=$(az cognitiveservices account show \
  -g "$RESOURCE_GROUP" -n "$AI_FOUNDRY_NAME" \
  --query "properties.endpoint" -o tsv 2>/dev/null || echo "")

# Key left empty — backend uses DefaultAzureCredential via managed identity
AI_KEY=""

SEARCH_ADMIN_KEY=$(az search admin-key show \
  -g "$RESOURCE_GROUP" --service-name "$AI_SEARCH_NAME" \
  --query primaryKey -o tsv 2>/dev/null || echo "")

# ─── Deploy code via SCP ─────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Deploying MCP Server + Streamlit code"
echo "=========================================="

STREAMLIT_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_STREAMLIT" -d --query publicIps -o tsv)
echo "  Streamlit VM IP: $STREAMLIT_IP"

# Upload backend code
echo "  Uploading backend/ ..."
scp -o StrictHostKeyChecking=no -r "$SCRIPT_DIR/../backend" "${ADMIN_USERNAME}@${STREAMLIT_IP}:/tmp/backend"

# Upload frontend code
echo "  Uploading frontend/ ..."
scp -o StrictHostKeyChecking=no -r "$SCRIPT_DIR/../frontend" "${ADMIN_USERNAME}@${STREAMLIT_IP}:/tmp/frontend"

# ─── Configure VM via run-command ─────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Configuring Streamlit VM"
echo "=========================================="

# Substitute credentials into setup script
cat > /tmp/setup-streamlit.sh << SETUPEOF
#!/bin/bash
set -e

# Wait for apt locks
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 5; done

# ─── Create app directories ────────────────────────
mkdir -p /opt/tcc/backend/tools
mkdir -p /opt/tcc/frontend

# Copy code from SCP upload
cp -r /tmp/backend/* /opt/tcc/backend/
cp -r /tmp/frontend/* /opt/tcc/frontend/

# ─── Create virtual environment ────────────────────
python3 -m venv /opt/tcc/venv
/opt/tcc/venv/bin/pip install -q --upgrade pip
/opt/tcc/venv/bin/pip install -q \
  mcp openai azure-search-documents azure-identity \
  "elasticsearch>=8.12.0,<9.0.0" \
  python-dotenv httpx streamlit

# ─── Write .env file ───────────────────────────────
cat > /opt/tcc/.env << 'ENVEOF'
ELASTICSEARCH_URL=http://${ES_IP}:9200
ELASTICSEARCH_INDEX=infrastructure-logs
AI_SEARCH_ENDPOINT=https://${AI_SEARCH_NAME}.search.windows.net
AI_SEARCH_KEY=${SEARCH_ADMIN_KEY}
AI_SEARCH_INDEX=${AI_SEARCH_INDEX}
AZURE_OPENAI_ENDPOINT=${AI_ENDPOINT}
AZURE_OPENAI_KEY=${AI_KEY}
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8080
MCP_SERVER_URL=http://localhost:8080
ENVEOF

# ─── MCP Server systemd service ────────────────────
cat > /etc/systemd/system/mcp-server.service << 'SVCEOF'
[Unit]
Description=TCC MCP Server (Model Context Protocol)
After=network.target

[Service]
User=root
WorkingDirectory=/opt/tcc/backend
EnvironmentFile=/opt/tcc/.env
ExecStart=/opt/tcc/venv/bin/python mcp_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

# ─── Streamlit systemd service ─────────────────────
cat > /etc/systemd/system/streamlit.service << 'SVCEOF'
[Unit]
Description=TCC Streamlit Frontend (Talk to Your Logs)
After=network.target mcp-server.service
Requires=mcp-server.service

[Service]
User=root
WorkingDirectory=/opt/tcc/frontend
EnvironmentFile=/opt/tcc/.env
ExecStart=/opt/tcc/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

# ─── Start services ────────────────────────────────
systemctl daemon-reload
systemctl enable mcp-server streamlit
systemctl start mcp-server
sleep 5
systemctl start streamlit
sleep 3

# Verify
echo "MCP Server status: \$(systemctl is-active mcp-server)"
echo "Streamlit status: \$(systemctl is-active streamlit)"

echo "Setup complete"
SETUPEOF

az vm run-command invoke \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_STREAMLIT" \
  --command-id RunShellScript \
  --scripts @/tmp/setup-streamlit.sh

echo "✅ Streamlit VM configured"

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Streamlit VM Details:"
echo "  Public IP:          $STREAMLIT_IP"
echo "  SSH:                ssh tccadmin@$STREAMLIT_IP  (key-based auth)"
echo "  Streamlit UI:       http://$STREAMLIT_IP:8501"
echo "  MCP Server:         http://$STREAMLIT_IP:8080  (backend)"
echo "=========================================="
