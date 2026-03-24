"""
Configuration for MCP Server backend.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Azure AI Search
AI_SEARCH_ENDPOINT = os.environ.get("AI_SEARCH_ENDPOINT", "https://search-tcc-poc.search.windows.net")
AI_SEARCH_KEY = os.environ.get("AI_SEARCH_KEY", "")
AI_SEARCH_INDEX = os.environ.get("AI_SEARCH_INDEX", "logs-index")

# Azure OpenAI / AI Foundry
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")

# Elasticsearch (direct access for real-time queries)
ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
ELASTICSEARCH_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "infrastructure-logs")

# MCP Server
MCP_SERVER_HOST = os.environ.get("MCP_SERVER_HOST", "0.0.0.0")
MCP_SERVER_PORT = int(os.environ.get("MCP_SERVER_PORT", "8080"))
