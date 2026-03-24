"""
MCP Tool: Analyze Logs using Azure AI Foundry (GPT-4o)

Takes log data and provides AI-powered analysis, root cause analysis,
and actionable recommendations.
"""
import json
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from config import (
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT,
)

SYSTEM_PROMPT = """You are an expert infrastructure and e-commerce operations AI assistant for TCC.
You analyze infrastructure logs from Zabbix monitoring, Elasticsearch, and the TCC e-commerce web application (Nginx + Flask).
Your job is to:
1. Identify patterns and anomalies in log data
2. Provide root cause analysis for errors and warnings
3. Suggest actionable remediation steps
4. Summarize log trends and health status
5. Correlate events across different hosts and services
6. Analyze e-commerce transaction logs (purchases, cart actions, payment failures)
7. Track customer purchase patterns and order success rates
8. Identify e-commerce performance issues (slow responses, payment gateway errors)

The monitored servers include:
- ecommerce-web-01: E-commerce web app (Nginx reverse proxy → Flask/Gunicorn)
- db-server-01: Database server (MySQL)
- app-server-01: Application server
- monitor-01: Zabbix monitoring server

Always be specific with hostnames, services, timestamps, metrics, and e-commerce data (order IDs, customer names, amounts).
Format your response in a clear, structured way."""


def get_openai_client() -> AzureOpenAI:
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2024-06-01",
    )


def analyze_logs(query: str, log_data: str) -> str:
    """Analyze log data using AI Foundry GPT-4o model.

    Args:
        query: The user's question or analysis request
        log_data: JSON string of log entries to analyze
    """
    client = get_openai_client()

    user_message = f"""User Question: {query}

Log Data:
{log_data}

Please analyze the above logs and provide insights based on the user's question."""

    response = client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content
