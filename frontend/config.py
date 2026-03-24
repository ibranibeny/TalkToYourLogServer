"""
Configuration for Streamlit frontend.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# MCP Server Backend
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080")

# Azure OpenAI (DefaultAzureCredential is used - no API key needed)
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")

# App settings
APP_TITLE = "TCC - Talk to Your Logs"
APP_ICON = "📊"
