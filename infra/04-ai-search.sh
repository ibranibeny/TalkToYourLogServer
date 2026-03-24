#!/bin/bash
# =============================================================================
# TCC PoC - 04 - Azure AI Search
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

echo "=========================================="
echo "Creating Azure AI Search: $AI_SEARCH_NAME"
echo "=========================================="

az search service create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$AI_SEARCH_NAME" \
  --sku "$AI_SEARCH_SKU" \
  --location "$LOCATION" \
  --partition-count 1 \
  --replica-count 1 \
  --tags $TAGS

echo "✅ Azure AI Search service created"

# Get the admin key for later configuration
SEARCH_ADMIN_KEY=$(az search admin-key show \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "$AI_SEARCH_NAME" \
  --query primaryKey -o tsv)

echo ""
echo "=========================================="
echo "AI Search Details:"
echo "  Endpoint: https://$AI_SEARCH_NAME.search.windows.net"
echo "  Admin Key: $SEARCH_ADMIN_KEY"
echo "=========================================="

# Create the logs index via REST API
echo "Creating search index: $AI_SEARCH_INDEX"

curl -s -X PUT "https://$AI_SEARCH_NAME.search.windows.net/indexes/$AI_SEARCH_INDEX?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "name": "'"$AI_SEARCH_INDEX"'",
    "fields": [
      { "name": "id", "type": "Edm.String", "key": true, "filterable": true },
      { "name": "timestamp", "type": "Edm.DateTimeOffset", "filterable": true, "sortable": true },
      { "name": "hostname", "type": "Edm.String", "filterable": true, "facetable": true },
      { "name": "severity", "type": "Edm.String", "filterable": true, "facetable": true },
      { "name": "service", "type": "Edm.String", "filterable": true, "facetable": true },
      { "name": "message", "type": "Edm.String", "searchable": true, "analyzer": "standard.lucene" },
      { "name": "source", "type": "Edm.String", "filterable": true },
      { "name": "category", "type": "Edm.String", "filterable": true, "facetable": true },
      { "name": "cpu_percent", "type": "Edm.Double", "filterable": true, "sortable": true },
      { "name": "memory_percent", "type": "Edm.Double", "filterable": true, "sortable": true },
      { "name": "disk_percent", "type": "Edm.Double", "filterable": true, "sortable": true },
      { "name": "ecommerce_action", "type": "Edm.String", "filterable": true, "facetable": true },
      { "name": "ecommerce_order_id", "type": "Edm.String", "filterable": true },
      { "name": "ecommerce_customer", "type": "Edm.String", "filterable": true, "facetable": true },
      { "name": "ecommerce_product", "type": "Edm.String", "searchable": true },
      { "name": "ecommerce_total", "type": "Edm.Double", "filterable": true, "sortable": true },
      { "name": "ecommerce_status", "type": "Edm.String", "filterable": true, "facetable": true },
      { "name": "content_vector", "type": "Collection(Edm.Single)", "searchable": true,
        "dimensions": 1536,
        "vectorSearchProfile": "my-vector-profile"
      }
    ],
    "vectorSearch": {
      "algorithms": [
        {
          "name": "my-hnsw",
          "kind": "hnsw",
          "hnswParameters": {
            "m": 4,
            "efConstruction": 400,
            "efSearch": 500,
            "metric": "cosine"
          }
        }
      ],
      "profiles": [
        {
          "name": "my-vector-profile",
          "algorithm": "my-hnsw"
        }
      ]
    },
    "semantic": {
      "configurations": [
        {
          "name": "my-semantic-config",
          "prioritizedFields": {
            "contentFields": [
              { "fieldName": "message" }
            ],
            "titleField": { "fieldName": "hostname" },
            "keywordsFields": [
              { "fieldName": "severity" },
              { "fieldName": "service" }
            ]
          }
        }
      ]
    }
  }'

echo ""
echo "✅ Search index '$AI_SEARCH_INDEX' created with vector search and semantic config"
