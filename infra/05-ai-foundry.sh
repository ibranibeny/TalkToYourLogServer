#!/bin/bash
# =============================================================================
# TCC PoC - 05 - Azure AI Foundry (Cognitive Services / OpenAI)
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

echo "=========================================="
echo "Creating Azure AI Services: $AI_FOUNDRY_NAME in $AI_FOUNDRY_LOCATION"
echo "=========================================="

# If the account already exists in a different region, delete + purge it first
EXISTING_LOCATION=$(az cognitiveservices account show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --query "location" -o tsv 2>/dev/null || true)

if [[ -n "$EXISTING_LOCATION" && "${EXISTING_LOCATION,,}" != "${AI_FOUNDRY_LOCATION,,}" ]]; then
  echo "Account exists in $EXISTING_LOCATION, moving to $AI_FOUNDRY_LOCATION..."
  az cognitiveservices account delete \
    --resource-group "$RESOURCE_GROUP" \
    --name "$AI_FOUNDRY_NAME"
  az cognitiveservices account purge \
    --resource-group "$RESOURCE_GROUP" \
    --name "$AI_FOUNDRY_NAME" \
    --location "$EXISTING_LOCATION"
fi

# Purge any lingering soft-deleted resource with this name
az cognitiveservices account purge \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --location "$AI_FOUNDRY_LOCATION" \
  2>/dev/null || true

# Create the AI Services account
az cognitiveservices account create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --kind "OpenAI" \
  --sku "$AI_FOUNDRY_SKU" \
  --location "$AI_FOUNDRY_LOCATION" \
  --tags $TAGS \
  --yes

echo "✅ AI Services account created"

echo "=========================================="
echo "Deploying GPT-4o Model"
echo "=========================================="

# Deploy GPT-4o model
az cognitiveservices account deployment create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --deployment-name "$AI_MODEL_DEPLOYMENT" \
  --model-name "$AI_MODEL_NAME" \
  --model-version "$AI_MODEL_VERSION" \
  --model-format "OpenAI" \
  --sku-capacity 10 \
  --sku-name "GlobalStandard"

echo "✅ GPT-4o model deployed"

# Deploy text-embedding-ada-002 for vector search
echo "=========================================="
echo "Deploying Embedding Model"
echo "=========================================="

az cognitiveservices account deployment create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --deployment-name "text-embedding-ada-002" \
  --model-name "text-embedding-ada-002" \
  --model-version "2" \
  --model-format "OpenAI" \
  --sku-capacity 10 \
  --sku-name "GlobalStandard"

echo "✅ Embedding model deployed"

# Get endpoint and key
AI_ENDPOINT=$(az cognitiveservices account show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --query "properties.endpoint" -o tsv)

AI_KEY=$(az cognitiveservices account keys list \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --query "key1" -o tsv)

echo "  Location: $AI_FOUNDRY_LOCATION"

echo ""
echo "=========================================="
echo "AI Foundry Details:"
echo "  Endpoint: $AI_ENDPOINT"
echo "  Key: $AI_KEY"
echo "  GPT-4o Deployment: $AI_MODEL_DEPLOYMENT"
echo "  Embedding Deployment: text-embedding-ada-002"
echo "=========================================="
