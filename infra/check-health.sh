#!/bin/bash
# =============================================================================
# TCC PoC - Health Check & Recovery Script
#
# 1. Ensures all VMs are running (starts stopped ones)
# 2. Lists all VMs with IPs and power state
# 3. Ensures NSG AllowAllInbound rule exists
# 4. Verifies services on each VM and restarts if needed
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

VM_LIST=("$VM_ELASTICSEARCH" "$VM_ZABBIX" "$VM_ECOMMERCE" "$VM_STREAMLIT")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. NSG Rules
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  NSG Rules Check${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"

for NSG in "$NSG_ONPREM" "$NSG_AZURE"; do
  if ! az network nsg show -g "$RESOURCE_GROUP" -n "$NSG" --query name -o tsv 2>/dev/null; then
    echo -e "  ${YELLOW}⚠️  NSG '$NSG' not found, skipping${NC}"
    continue
  fi

  # Check AllowAllInbound
  if az network nsg rule show -g "$RESOURCE_GROUP" --nsg-name "$NSG" -n AllowAllInbound --query name -o tsv 2>/dev/null; then
    echo -e "  ${GREEN}✅ $NSG: AllowAllInbound exists${NC}"
  else
    echo -e "  ${YELLOW}⚠️  $NSG: AllowAllInbound missing — creating...${NC}"
    az network nsg rule create \
      --resource-group "$RESOURCE_GROUP" \
      --nsg-name "$NSG" \
      --name AllowAllInbound \
      --priority 100 \
      --direction Inbound \
      --access Allow \
      --protocol "*" \
      --source-address-prefix "*" \
      --source-port-range "*" \
      --destination-address-prefix "*" \
      --destination-port-range "*" \
      -o none
    echo -e "  ${GREEN}✅ $NSG: AllowAllInbound created${NC}"
  fi

  # Check AllowAllOutbound
  if az network nsg rule show -g "$RESOURCE_GROUP" --nsg-name "$NSG" -n AllowAllOutbound --query name -o tsv 2>/dev/null; then
    echo -e "  ${GREEN}✅ $NSG: AllowAllOutbound exists${NC}"
  else
    echo -e "  ${YELLOW}⚠️  $NSG: AllowAllOutbound missing — creating...${NC}"
    az network nsg rule create \
      --resource-group "$RESOURCE_GROUP" \
      --nsg-name "$NSG" \
      --name AllowAllOutbound \
      --priority 100 \
      --direction Outbound \
      --access Allow \
      --protocol "*" \
      --source-address-prefix "*" \
      --source-port-range "*" \
      --destination-address-prefix "*" \
      --destination-port-range "*" \
      -o none
    echo -e "  ${GREEN}✅ $NSG: AllowAllOutbound created${NC}"
  fi
done

# ═══════════════════════════════════════════════════════════════════════════════
# 2. VM Power State — start any stopped VMs
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  VM Power State Check${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"

for VM in "${VM_LIST[@]}"; do
  POWER_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM" \
    --query "instanceView.statuses[?starts_with(code,'PowerState/')].displayStatus" \
    -o tsv 2>/dev/null || echo "Not Found")

  if [[ "$POWER_STATE" == "VM running" ]]; then
    echo -e "  ${GREEN}✅ $VM: Running${NC}"
  elif [[ "$POWER_STATE" == "Not Found" ]]; then
    echo -e "  ${RED}❌ $VM: Not found in resource group${NC}"
  else
    echo -e "  ${YELLOW}⚠️  $VM: $POWER_STATE — starting...${NC}"
    az vm start -g "$RESOURCE_GROUP" -n "$VM" --no-wait
    echo -e "  ${GREEN}✅ $VM: Start command sent${NC}"
  fi
done

# Wait for any VMs that were just started
NEED_WAIT=false
for VM in "${VM_LIST[@]}"; do
  POWER_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM" \
    --query "instanceView.statuses[?starts_with(code,'PowerState/')].displayStatus" \
    -o tsv 2>/dev/null || echo "Not Found")
  if [[ "$POWER_STATE" != "VM running" && "$POWER_STATE" != "Not Found" ]]; then
    NEED_WAIT=true
    break
  fi
done

if [[ "$NEED_WAIT" == "true" ]]; then
  echo ""
  echo "  Waiting for VMs to finish starting..."
  for VM in "${VM_LIST[@]}"; do
    az vm wait -g "$RESOURCE_GROUP" -n "$VM" --custom "instanceView.statuses[?code=='PowerState/running']" 2>/dev/null || true
  done
  echo -e "  ${GREEN}✅ All VMs running${NC}"
  echo "  Waiting 30s for services to initialize..."
  sleep 30
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 3. List VMs with IPs
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  VM Inventory${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo ""
printf "  %-22s %-18s %-14s %-12s\n" "VM Name" "Public IP" "Private IP" "Status"
printf "  %-22s %-18s %-14s %-12s\n" "──────────────────────" "────────────────" "──────────────" "────────────"

for VM in "${VM_LIST[@]}"; do
  INFO=$(az vm show -g "$RESOURCE_GROUP" -n "$VM" -d \
    --query "{pip:publicIps, prip:privateIps}" -o tsv 2>/dev/null || echo "N/A	N/A")
  PUBLIC_IP=$(echo "$INFO" | cut -f1)
  PRIVATE_IP=$(echo "$INFO" | cut -f2)
  POWER_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM" \
    --query "instanceView.statuses[?starts_with(code,'PowerState/')].displayStatus" \
    -o tsv 2>/dev/null || echo "Unknown")

  if [[ "$POWER_STATE" == "VM running" ]]; then
    STATUS="${GREEN}Running${NC}"
  else
    STATUS="${RED}$POWER_STATE${NC}"
  fi
  printf "  %-22s %-18s %-14s " "$VM" "$PUBLIC_IP" "$PRIVATE_IP"
  echo -e "$STATUS"
done

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Service Health Checks (via az vm run-command)
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Service Health Checks${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"

check_and_restart_services() {
  local vm_name="$1"
  shift
  local services=("$@")

  # Check if VM exists and is running
  POWER_STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$vm_name" \
    --query "instanceView.statuses[?starts_with(code,'PowerState/')].displayStatus" \
    -o tsv 2>/dev/null || echo "Not Found")

  if [[ "$POWER_STATE" != "VM running" ]]; then
    echo -e "  ${RED}❌ $vm_name: Skipping — $POWER_STATE${NC}"
    return
  fi

  echo ""
  echo -e "  ${CYAN}── $vm_name ──${NC}"

  # Build check + restart script
  local script="#!/bin/bash\n"
  for svc in "${services[@]}"; do
    script+="STATUS_${svc//[-.]/_}=\$(systemctl is-active $svc 2>/dev/null || echo 'inactive')\n"
    script+="echo \"$svc: \$STATUS_${svc//[-.]/_}\"\n"
    script+="if [ \"\$STATUS_${svc//[-.]/_}\" != 'active' ]; then\n"
    script+="  echo \"  Restarting $svc...\"\n"
    script+="  systemctl start $svc 2>/dev/null || echo \"  Failed to start $svc\"\n"
    script+="  sleep 3\n"
    script+="  NEW_STATUS=\$(systemctl is-active $svc 2>/dev/null || echo 'inactive')\n"
    script+="  echo \"  $svc after restart: \$NEW_STATUS\"\n"
    script+="fi\n"
  done

  RESULT=$(az vm run-command invoke \
    --resource-group "$RESOURCE_GROUP" \
    --name "$vm_name" \
    --command-id RunShellScript \
    --scripts "$(echo -e "$script")" \
    --query "value[0].message" -o tsv 2>/dev/null || echo "ERROR: Could not reach VM")

  # Parse and colorize output
  while IFS= read -r line; do
    if [[ -z "$line" ]]; then continue; fi
    if echo "$line" | grep -q ": active"; then
      echo -e "     ${GREEN}✅ $line${NC}"
    elif echo "$line" | grep -q "Restarting"; then
      echo -e "     ${YELLOW}🔄 $line${NC}"
    elif echo "$line" | grep -q "after restart: active"; then
      echo -e "     ${GREEN}✅ $line${NC}"
    elif echo "$line" | grep -q "after restart:"; then
      echo -e "     ${RED}❌ $line${NC}"
    elif echo "$line" | grep -q ": inactive\|: failed"; then
      echo -e "     ${RED}❌ $line${NC}"
    else
      echo "     $line"
    fi
  done <<< "$RESULT"
}

# Elasticsearch VM: elasticsearch, kibana, logstash
check_and_restart_services "$VM_ELASTICSEARCH" elasticsearch kibana logstash

# Zabbix VM: mysql, zabbix-server, zabbix-agent, apache2
check_and_restart_services "$VM_ZABBIX" mysql zabbix-server zabbix-agent apache2

# E-Commerce VM: ecommerce (gunicorn), nginx, zabbix-agent
check_and_restart_services "$VM_ECOMMERCE" ecommerce nginx zabbix-agent

# Streamlit VM: mcp-server, streamlit
check_and_restart_services "$VM_STREAMLIT" mcp-server streamlit

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Quick Endpoint Verification
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Endpoint Verification${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo ""

ES_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ELASTICSEARCH" -d --query publicIps -o tsv 2>/dev/null || echo "")
ZABBIX_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ZABBIX" -d --query publicIps -o tsv 2>/dev/null || echo "")
ECOMMERCE_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_ECOMMERCE" -d --query publicIps -o tsv 2>/dev/null || echo "")
STREAMLIT_IP=$(az vm show -g "$RESOURCE_GROUP" -n "$VM_STREAMLIT" -d --query publicIps -o tsv 2>/dev/null || echo "")

check_endpoint() {
  local label="$1"
  local url="$2"
  local ip="$3"

  if [[ -z "$ip" ]]; then
    echo -e "  ${RED}❌ $label: No IP available${NC}"
    return 1
  fi

  HTTP_CODE=$(python3 -c "
import urllib.request
try:
    r = urllib.request.urlopen('$url', timeout=5)
    print(r.getcode())
except Exception as e:
    print('FAIL')
" 2>/dev/null)

  if [[ "$HTTP_CODE" =~ ^[23] ]]; then
    echo -e "  ${GREEN}✅ $label: HTTP $HTTP_CODE  →  $url${NC}"
    return 0
  else
    echo -e "  ${RED}❌ $label: $HTTP_CODE  →  $url${NC}"
    return 1
  fi
}

# Helper: force-open all NSG inbound rules
fix_all_nsg() {
  for NSG in "$NSG_ONPREM" "$NSG_AZURE"; do
    az network nsg show -g "$RESOURCE_GROUP" -n "$NSG" --query name -o tsv 2>/dev/null || continue
    if ! az network nsg rule show -g "$RESOURCE_GROUP" --nsg-name "$NSG" -n AllowAllInbound --query name -o tsv 2>/dev/null; then
      echo -e "  ${YELLOW}⚠️  $NSG: AllowAllInbound missing — recreating...${NC}"
      az network nsg rule create \
        --resource-group "$RESOURCE_GROUP" \
        --nsg-name "$NSG" \
        --name AllowAllInbound \
        --priority 100 \
        --direction Inbound \
        --access Allow \
        --protocol "*" \
        --source-address-prefix "*" \
        --source-port-range "*" \
        --destination-address-prefix "*" \
        --destination-port-range "*" \
        -o none 2>/dev/null
      echo -e "  ${GREEN}✅ $NSG: AllowAllInbound restored${NC}"
    fi
    if ! az network nsg rule show -g "$RESOURCE_GROUP" --nsg-name "$NSG" -n AllowAllOutbound --query name -o tsv 2>/dev/null; then
      az network nsg rule create \
        --resource-group "$RESOURCE_GROUP" \
        --nsg-name "$NSG" \
        --name AllowAllOutbound \
        --priority 100 \
        --direction Outbound \
        --access Allow \
        --protocol "*" \
        --source-address-prefix "*" \
        --source-port-range "*" \
        --destination-address-prefix "*" \
        --destination-port-range "*" \
        -o none 2>/dev/null
    fi
  done
}

# Run endpoint checks with auto-retry: if any fail, fix NSG and retry once
FAIL_COUNT=0
ENDPOINTS=(
  "Elasticsearch|http://$ES_IP:9200|$ES_IP"
  "Kibana|http://$ES_IP:5601|$ES_IP"
  "Zabbix|http://$ZABBIX_IP/zabbix|$ZABBIX_IP"
  "E-Commerce|http://$ECOMMERCE_IP/health|$ECOMMERCE_IP"
  "Streamlit UI|http://$STREAMLIT_IP:8501|$STREAMLIT_IP"
)

for ep in "${ENDPOINTS[@]}"; do
  IFS='|' read -r label url ip <<< "$ep"
  check_endpoint "$label" "$url" "$ip" || ((FAIL_COUNT++))
done

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo ""
  echo -e "  ${YELLOW}⚠️  $FAIL_COUNT endpoint(s) unreachable — fixing NSG rules and retrying...${NC}"
  fix_all_nsg
  echo "  Waiting 10s for NSG propagation..."
  sleep 10

  echo ""
  echo -e "${CYAN}  Endpoint Verification (retry)${NC}"
  echo ""
  for ep in "${ENDPOINTS[@]}"; do
    IFS='|' read -r label url ip <<< "$ep"
    check_endpoint "$label" "$url" "$ip" || true
  done
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Quick Access${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo ""
echo "  Elasticsearch:  http://$ES_IP:9200"
echo "  Kibana:         http://$ES_IP:5601"
echo "  Zabbix:         http://$ZABBIX_IP/zabbix  (Admin / zabbix)"
echo "  E-Commerce:     http://$ECOMMERCE_IP"
echo "  Streamlit:      http://$STREAMLIT_IP:8501"
echo ""
echo "  SSH:            ssh tccadmin@<ip>"
echo ""
