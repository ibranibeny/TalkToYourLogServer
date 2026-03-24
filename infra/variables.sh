#!/bin/bash
# =============================================================================
# TCC PoC - Environment Variables
# =============================================================================

# Azure Subscription
export SUBSCRIPTION_ID="<your-subscription-id>"

# Resource Group
export RESOURCE_GROUP="rg-tcc-poc"
export LOCATION="southeastasia"

# Tags
export TAGS="project=tcc-poc environment=dev owner=tcc"

# Networking
export VNET_NAME="vnet-tcc-poc"
export VNET_PREFIX="10.0.0.0/16"
export SUBNET_ONPREM="subnet-onprem"
export SUBNET_ONPREM_PREFIX="10.0.1.0/24"
export SUBNET_AZURE="subnet-azure"
export SUBNET_AZURE_PREFIX="10.0.2.0/24"
export NSG_ONPREM="nsg-onprem"
export NSG_AZURE="nsg-azure"

# On-Prem Simulation VMs
export VM_ZABBIX="vm-zabbix"
export VM_ELASTICSEARCH="vm-elasticsearch"
export VM_ECOMMERCE="vm-ecommerce"
export VM_STREAMLIT="vm-streamlit"
export VM_SIZE="Standard_B2ms"
export VM_IMAGE="Ubuntu2204"
export ADMIN_USERNAME="tccadmin"
# Note: Use SSH key or set password securely via env var
# export ADMIN_PASSWORD="<set-securely>"

# Azure AI Search
export AI_SEARCH_NAME="search-tcc-poc"
export AI_SEARCH_SKU="basic"
export AI_SEARCH_INDEX="logs-index"

# Azure AI Foundry (OpenAI)
export AI_FOUNDRY_NAME="ai-tcc-poc"
export AI_FOUNDRY_SKU="S0"
export AI_FOUNDRY_LOCATION="eastus"  # GPT-4o GlobalStandard requires eastus (not available in southeastasia)
export AI_MODEL_DEPLOYMENT="gpt-4o"
export AI_MODEL_NAME="gpt-4o"
export AI_MODEL_VERSION="2024-08-06"

# Function App (Ingestion)
export STORAGE_ACCOUNT="sttccpoc2025"
export FUNCTION_APP_NAME="func-tcc-poc-ingestion"
export FUNCTION_APP_PLAN="plan-tcc-poc-ingestion"
export FUNCTION_RUNTIME="python"
export FUNCTION_VERSION="4"

# E-Commerce Config (on the VM)
export ECOMMERCE_APP_PORT="5000"
export NGINX_PORT="80"

# Elasticsearch Config (on the VM)
export ES_PORT="9200"
export ES_VERSION="8.12.0"
export KIBANA_PORT="5601"

# Zabbix Config (on the VM)
export ZABBIX_VERSION="6.4"

# E-Commerce App Config (on the VM)
export ECOMMERCE_APP_PORT="5000"
export NGINX_PORT="80"
