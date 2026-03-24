"""
Configuration for Elasticsearch to Azure AI Search ingestion.
"""
import os

# Elasticsearch (on-prem / simulated)
ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
ES_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "infrastructure-logs")

# Azure AI Search
AI_SEARCH_ENDPOINT = os.environ.get("AI_SEARCH_ENDPOINT", "https://search-tcc-poc.search.windows.net")
AI_SEARCH_KEY = os.environ.get("AI_SEARCH_KEY", "")
AI_SEARCH_INDEX = os.environ.get("AI_SEARCH_INDEX", "logs-index")

# Azure OpenAI (for embeddings)
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

# Sync settings
SYNC_INTERVAL_SECONDS = int(os.environ.get("SYNC_INTERVAL_SECONDS", "30"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))
