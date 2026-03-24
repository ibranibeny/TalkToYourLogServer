#!/bin/bash
# =============================================================================
# TCC PoC - 01 - Resource Group
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

echo "=========================================="
echo "Creating Resource Group: $RESOURCE_GROUP"
echo "=========================================="

az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --tags $TAGS

echo "✅ Resource group '$RESOURCE_GROUP' created in '$LOCATION'"
