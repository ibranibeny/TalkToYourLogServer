#!/bin/bash
# =============================================================================
# TCC PoC - Destroy All Resources
# Deletes the entire resource group and all resources within it
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

echo "============================================================"
echo "  TCC PoC - Resource Destruction"
echo "============================================================"
echo ""
echo "⚠️  This will permanently delete ALL resources in:"
echo "    Resource Group: $RESOURCE_GROUP"
echo "    Location:       $LOCATION"
echo ""
echo "  Resources to be deleted:"
echo "    - VM: $VM_ELASTICSEARCH (Elasticsearch + Kibana)"
echo "    - VM: $VM_ZABBIX (Zabbix monitoring)"
echo "    - VM: $VM_ECOMMERCE (E-Commerce Nginx + Flask)"
echo "    - Azure AI Search: $AI_SEARCH_NAME"
echo "    - Azure AI Foundry: $AI_FOUNDRY_NAME"
echo "    - Function App: $FUNCTION_APP_NAME"
echo "    - VNet: $VNET_NAME (+ subnets, NSGs)"
echo "    - Storage Account, Disks, NICs, Public IPs, etc."
echo ""

read -p "Are you sure you want to DELETE everything? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted. No resources deleted."
    exit 0
fi

echo ""
echo "Deleting resource group '$RESOURCE_GROUP'..."
az group delete \
  --name "$RESOURCE_GROUP" \
  --yes \
  --no-wait

echo ""
echo "============================================================"
echo "  ✅ Deletion initiated (running in background)"
echo "============================================================"
echo ""
echo "The resource group is being deleted asynchronously."
echo "This may take 5-10 minutes to complete."
echo ""
echo "To check status:"
echo "  az group show --name $RESOURCE_GROUP --query 'properties.provisioningState' -o tsv"
echo ""
echo "To verify it's fully deleted:"
echo "  az group exists --name $RESOURCE_GROUP"
