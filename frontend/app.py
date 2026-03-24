"""
TCC PoC - Streamlit Frontend
Talk to Your Infrastructure Logs with AI

Chat interface that connects to the MCP server backend to query,
search, and analyze infrastructure logs using natural language.
"""
import json
import streamlit as st
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import httpx

from config import (
    MCP_SERVER_URL,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_CHAT_DEPLOYMENT,
    APP_TITLE,
    APP_ICON,
)

# Page config
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
)

# ─── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.markdown("---")
    st.markdown("### Quick Actions")

    if st.button("🔴 Show Critical Alerts"):
        st.session_state.quick_query = "Show me all critical alerts from the last 6 hours"

    if st.button("📊 System Health Summary"):
        st.session_state.quick_query = "Give me an overall system health summary"

    if st.button("🖥️ High CPU Servers"):
        st.session_state.quick_query = "Which servers have high CPU usage above 80%?"

    if st.button("⚠️ Recent Errors"):
        st.session_state.quick_query = "Show me recent error logs across all services"

    if st.button("🔍 Service Status"):
        st.session_state.quick_query = "What is the status of all monitored services?"

    st.markdown("---")
    st.markdown("### E-Commerce")

    if st.button("🛒 Recent Orders"):
        st.session_state.quick_query = "Show me all recent e-commerce orders and their payment status"

    if st.button("💳 Payment Failures"):
        st.session_state.quick_query = "Show me all failed payment transactions in the last 24 hours"

    if st.button("📦 Top Products"):
        st.session_state.quick_query = "Which products are being purchased the most?"

    st.markdown("---")
    st.markdown("### Filters")
    severity_filter = st.selectbox("Severity", ["All", "INFO", "WARNING", "ERROR", "CRITICAL"])
    hostname_filter = st.text_input("Hostname", placeholder="e.g., ecommerce-web-01")
    service_filter = st.text_input("Service", placeholder="e.g., nginx, mysql")

    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
    This PoC demonstrates natural language querying of infrastructure and e-commerce logs from:
    - **Zabbix** (on-prem monitoring)
    - **Elasticsearch** (centralized logging)
    - **TCC Shop** (e-commerce web app on Nginx)

    Powered by:
    - Azure AI Foundry (GPT-4o)
    - Azure AI Search
    - MCP Server backend
    """)

# ─── MCP Server Tools ─────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_infrastructure_logs",
            "description": "Search infrastructure logs using natural language with semantic search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "severity": {"type": "string", "enum": ["INFO", "WARNING", "ERROR", "CRITICAL"]},
                    "hostname": {"type": "string"},
                    "service": {"type": "string"},
                    "top": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_log_data",
            "description": "Analyze log data using AI for patterns, root causes, and recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Analysis question"},
                    "log_data": {"type": "string", "description": "Log data to analyze (JSON)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_alerts",
            "description": "Get recent Zabbix monitoring alerts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["WARNING", "ERROR", "CRITICAL"]},
                    "hostname": {"type": "string"},
                    "hours": {"type": "integer", "default": 24},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_health_summary",
            "description": "Get overall health summary of all monitored systems including e-commerce.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ecommerce_transactions",
            "description": "Get e-commerce transaction logs: purchases, cart actions, payment outcomes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["page_view", "add_to_cart", "checkout"]},
                    "customer": {"type": "string"},
                    "order_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["success", "payment_failed", "out_of_stock", "empty_cart"]},
                    "hours": {"type": "integer", "default": 24},
                    "limit": {"type": "integer", "default": 30},
                },
            },
        },
    },
]

SYSTEM_MESSAGE = """You are an AI infrastructure and e-commerce operations assistant for TCC.
You help users explore and understand their infrastructure logs from Zabbix monitoring,
Elasticsearch, and the TCC Shop e-commerce web application (running on Nginx + Flask/Gunicorn).
You have access to tools that can:

1. Search logs using natural language (semantic + vector search via Azure AI Search)
2. Analyze log patterns and provide root cause analysis (via Azure AI Foundry GPT-4o)
3. Retrieve recent Zabbix alerts
4. Generate system health summaries (including e-commerce health)
5. Query e-commerce transaction logs (purchases, cart actions, payment status)

The monitored servers include:
- ecommerce-web-01: E-commerce web app (Nginx → Flask/Gunicorn)
- db-server-01: Database server
- app-server-01: Application server
- monitor-01: Zabbix monitoring

Always use the appropriate tools to answer questions. Be specific with data points.
Present results in a clear, organized format with tables when appropriate."""


def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Call a tool on the MCP server backend via MCP Streamable HTTP (JSON-RPC).

    MCP Streamable HTTP requires an initialize handshake before tool calls.
    Each invocation opens a fresh session: initialize → initialized → tools/call.
    The server returns responses in SSE format (event: message\\ndata: {...}).
    """
    mcp_url = f"{MCP_SERVER_URL}/mcp"

    def parse_sse_json(text: str) -> dict:
        """Parse SSE response and extract JSON-RPC result from data: lines."""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                try:
                    return json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
        # Fallback: try parsing the whole text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    try:
        with httpx.Client(timeout=60) as client:
            # MCP Streamable HTTP requires this Accept header on ALL requests
            mcp_headers = {
                "Accept": "application/json, text/event-stream",
            }

            # Step 1: Initialize session
            init_resp = client.post(
                mcp_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "tcc-frontend", "version": "1.0.0"},
                    },
                },
                headers=mcp_headers,
            )
            init_resp.raise_for_status()
            session_id = init_resp.headers.get("Mcp-Session-Id", "")

            if session_id:
                mcp_headers["Mcp-Session-Id"] = session_id

            # Step 2: Send initialized notification
            client.post(
                mcp_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
                headers=mcp_headers,
            )

            # Step 3: Call the tool
            response = client.post(
                mcp_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                },
                headers=mcp_headers,
            )
            response.raise_for_status()

            result = parse_sse_json(response.text)
            if "result" in result:
                content = result["result"].get("content", [{}])
                return content[0].get("text", "No response") if content else "No response"
            elif "error" in result:
                return f"MCP error: {result['error'].get('message', 'Unknown error')}"
            return f"Unexpected response: {response.text[:200]}"
    except Exception as e:
        return f"Error calling MCP server: {e}"


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


def process_message(user_message: str) -> str:
    """Process user message through GPT-4o with tool calling."""
    client = get_openai_client()

    # Apply sidebar filters to context
    filter_context = ""
    if severity_filter != "All":
        filter_context += f" Filter by severity: {severity_filter}."
    if hostname_filter:
        filter_context += f" Filter by hostname: {hostname_filter}."
    if service_filter:
        filter_context += f" Filter by service: {service_filter}."

    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        *st.session_state.messages,
        {"role": "user", "content": user_message + filter_context},
    ]

    # First call - might request tool use
    response = client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.3,
    )

    assistant_msg = response.choices[0].message

    # Handle tool calls
    if assistant_msg.tool_calls:
        messages.append(assistant_msg)

        for tool_call in assistant_msg.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            with st.status(f"🔧 Calling: {tool_name}...", expanded=False):
                st.json(tool_args)
                tool_result = call_mcp_tool(tool_name, tool_args)
                st.text(tool_result[:500] + "..." if len(tool_result) > 500 else tool_result)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

        # Second call - synthesize tool results
        final_response = client.chat.completions.create(
            model=AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=messages,
            temperature=0.3,
        )
        return final_response.choices[0].message.content

    return assistant_msg.content


# ─── Main Chat Interface ──────────────────────────────────────
st.title(f"{APP_ICON} Talk to Your Infrastructure Logs")
st.caption("Ask questions about your infrastructure logs, e-commerce transactions, monitoring alerts, and system health")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle quick actions
if "quick_query" in st.session_state:
    prompt = st.session_state.quick_query
    del st.session_state.quick_query

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = process_message(prompt)
            st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# Chat input
if prompt := st.chat_input("Ask about your logs... (e.g., 'Show failed payments' or 'Critical errors on ecommerce-web-01')"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing your logs..."):
            response = process_message(prompt)
            st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
