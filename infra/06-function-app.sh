#!/bin/bash
# =============================================================================
# TCC PoC - 06 - Function App for ES → AI Search Vectorization
#
# Creates Azure Function App that polls Elasticsearch, generates
# vector embeddings via Azure OpenAI, and pushes to AI Search.
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

echo "=========================================="
echo "Creating Storage Account for Function App"
echo "=========================================="

az storage account create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$STORAGE_ACCOUNT" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --https-only true \
  --min-tls-version TLS1_2 \
  --tags $TAGS

echo "✅ Storage account created: $STORAGE_ACCOUNT"

echo "=========================================="
echo "Creating App Service Plan: $FUNCTION_APP_PLAN"
echo "=========================================="

# Use App Service Plan (B1) instead of consumption plan
# Consumption plan requires shared-key file share creation which is blocked by subscription policy
az appservice plan create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP_PLAN" \
  --location "$LOCATION" \
  --sku B1 \
  --is-linux

echo "✅ App Service Plan created"

echo "=========================================="
echo "Creating Function App: $FUNCTION_APP_NAME"
echo "=========================================="

az functionapp create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP_NAME" \
  --storage-account "$STORAGE_ACCOUNT" \
  --plan "$FUNCTION_APP_PLAN" \
  --runtime "$FUNCTION_RUNTIME" \
  --runtime-version "3.10" \
  --functions-version "$FUNCTION_VERSION" \
  --os-type Linux \
  --tags $TAGS

echo "✅ Function App created"

# Configure app settings
SEARCH_ADMIN_KEY=$(az search admin-key show \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$AI_SEARCH_NAME" \
  --query primaryKey -o tsv)

ES_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ELASTICSEARCH" -d --query publicIps -o tsv)

# Get Azure OpenAI endpoint and key
AI_ENDPOINT=$(az cognitiveservices account show \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --query "properties.endpoint" -o tsv)

AI_KEY=$(az cognitiveservices account keys list \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_FOUNDRY_NAME" \
  --query "key1" -o tsv)

az functionapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP_NAME" \
  --settings \
    "ELASTICSEARCH_URL=http://$ES_IP:9200" \
    "ELASTICSEARCH_INDEX=infrastructure-logs" \
    "AI_SEARCH_ENDPOINT=https://$AI_SEARCH_NAME.search.windows.net" \
    "AI_SEARCH_KEY=$SEARCH_ADMIN_KEY" \
    "AI_SEARCH_INDEX=$AI_SEARCH_INDEX" \
    "AZURE_OPENAI_ENDPOINT=$AI_ENDPOINT" \
    "AZURE_OPENAI_KEY=$AI_KEY" \
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002" \
    "BATCH_SIZE=100" \
    "SYNC_LOOKBACK_MINUTES=10"

echo "✅ Function App configured with ES, AI Search, and Azure OpenAI settings"

# Deploy function code
echo ""
echo "=========================================="
echo "Deploying Function App code"
echo "=========================================="

FUNC_DIR="$SCRIPT_DIR/../function-app"
if [ -d "$FUNC_DIR" ]; then
  cd "$FUNC_DIR"

  # Create .funcignore if not present
  [ -f .funcignore ] || cat > .funcignore << 'EOF'
.git*
.vscode
__pycache__
.venv
local.settings.json
test
EOF

  # Build zip package using Python (no external zip tool needed)
  DEPLOY_ZIP="/tmp/func-deploy-$$.zip"
  python3 -c "
import zipfile, os
with zipfile.ZipFile('$DEPLOY_ZIP', 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', '.venv', '.vscode')]
        for f in files:
            if not f.endswith('.pyc'):
                filepath = os.path.join(root, f)
                zf.write(filepath)
print('Zip created with', len(zf.namelist()), 'files')
"

  # Deploy via az CLI (no func CLI needed)
  az functionapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FUNCTION_APP_NAME" \
    --src "$DEPLOY_ZIP"

  cd "$SCRIPT_DIR"
  echo "✅ Function App code deployed"
else
  echo "⚠️  function-app/ directory not found, skipping code deployment"
fi

echo ""
echo "=========================================="
echo "Function App Details:"
echo "  URL: https://$FUNCTION_APP_NAME.azurewebsites.net"
echo "  Timer: Runs every 5 minutes"
echo "  Flow: ES → Vectorize (Azure OpenAI) → AI Search"
echo "=========================================="
