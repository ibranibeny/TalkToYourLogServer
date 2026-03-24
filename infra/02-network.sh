#!/bin/bash
# =============================================================================
# TCC PoC - 02 - Network (VNet, Subnets, NSGs)
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

echo "=========================================="
echo "Creating Virtual Network and Subnets"
echo "=========================================="

# Create VNet
az network vnet create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VNET_NAME" \
  --address-prefix "$VNET_PREFIX" \
  --tags $TAGS

# Create On-Prem Simulation Subnet
az network vnet subnet create \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --name "$SUBNET_ONPREM" \
  --address-prefix "$SUBNET_ONPREM_PREFIX"

# Create Azure Services Subnet
az network vnet subnet create \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --name "$SUBNET_AZURE" \
  --address-prefix "$SUBNET_AZURE_PREFIX"

echo "✅ VNet and subnets created"

echo "=========================================="
echo "Creating Network Security Groups"
echo "=========================================="

# NSG for On-Prem subnet
az network nsg create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$NSG_ONPREM" \
  --tags $TAGS

# Allow ALL inbound traffic from anywhere (PoC only - not for production)
az network nsg rule create \
  --resource-group "$RESOURCE_GROUP" \
  --nsg-name "$NSG_ONPREM" \
  --name "AllowAllInbound" \
  --priority 100 \
  --direction Inbound \
  --access Allow \
  --protocol "*" \
  --source-address-prefixes "*" \
  --source-port-ranges "*" \
  --destination-address-prefixes "*" \
  --destination-port-ranges "*" \
  --description "Allow all inbound traffic from anywhere (PoC only - SSH, HTTP, ES, Kibana, Logstash, Zabbix)"

# Allow ALL outbound traffic (PoC only)
az network nsg rule create \
  --resource-group "$RESOURCE_GROUP" \
  --nsg-name "$NSG_ONPREM" \
  --name "AllowAllOutbound" \
  --priority 100 \
  --direction Outbound \
  --access Allow \
  --protocol "*" \
  --source-address-prefixes "*" \
  --source-port-ranges "*" \
  --destination-address-prefixes "*" \
  --destination-port-ranges "*" \
  --description "Allow all outbound traffic (PoC only)"

# Associate NSG with on-prem subnet
az network vnet subnet update \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --name "$SUBNET_ONPREM" \
  --network-security-group "$NSG_ONPREM"

# NSG for Azure subnet
az network nsg create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$NSG_AZURE" \
  --tags $TAGS

az network vnet subnet update \
  --resource-group "$RESOURCE_GROUP" \
  --vnet-name "$VNET_NAME" \
  --name "$SUBNET_AZURE" \
  --network-security-group "$NSG_AZURE"

echo "✅ NSGs created and associated with subnets"
