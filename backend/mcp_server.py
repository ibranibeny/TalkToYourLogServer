"""
TCC PoC - MCP Server (Model Context Protocol)

Backend server that exposes tools for querying and analyzing
infrastructure logs via Azure AI Search and AI Foundry.
"""
import json
import logging

from mcp.server.fastmcp import FastMCP

from tools.search_logs import search_logs
from tools.analyze_logs import analyze_logs
from tools.zabbix_alerts import get_zabbix_alerts
from tools.ecommerce_logs import get_ecommerce_logs

from config import MCP_SERVER_HOST, MCP_SERVER_PORT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("TCC Log Analytics", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)


@mcp.tool()
def search_infrastructure_logs(
    query: str,
    severity: str | None = None,
    hostname: str | None = None,
    service: str | None = None,
    top: int = 10,
) -> str:
    """Search infrastructure logs using natural language.

    Search across all indexed logs from Zabbix and Elasticsearch using
    semantic search powered by Azure AI Search.

    Args:
        query: Natural language search query (e.g., "high CPU errors on web servers" or "failed payment orders")
        severity: Filter by log severity: INFO, WARNING, ERROR, or CRITICAL
        hostname: Filter by specific hostname (e.g., "ecommerce-web-01", "db-server-01")
        service: Filter by service name (e.g., "nginx", "mysql", "docker", "gunicorn")
        top: Number of results to return (default 10, max 50)
    """
    logger.info(f"Searching logs: query='{query}', severity={severity}, host={hostname}")
    return search_logs(query, severity=severity, hostname=hostname, service=service, top=min(top, 50))


@mcp.tool()
def analyze_log_data(query: str, log_data: str = "") -> str:
    """Analyze infrastructure logs using AI to find patterns, root causes, and recommendations.

    Provide log data or search results and ask questions about them.
    The AI will identify patterns, anomalies, and provide actionable insights.

    Args:
        query: Your question about the logs (e.g., "What caused the outage last night?")
        log_data: JSON string of log entries to analyze. If empty, will search first.
    """
    logger.info(f"Analyzing logs: query='{query}'")

    # If no log data provided, search for relevant logs first
    if not log_data:
        log_data = search_logs(query, top=20)

    return analyze_logs(query, log_data)


@mcp.tool()
def get_recent_alerts(
    severity: str | None = None,
    hostname: str | None = None,
    hours: int = 24,
    limit: int = 20,
) -> str:
    """Get recent Zabbix monitoring alerts from Elasticsearch.

    Retrieve recent alerts and monitoring events from the on-premises
    Zabbix monitoring system.

    Args:
        severity: Filter by severity: WARNING, ERROR, or CRITICAL
        hostname: Filter by specific hostname
        hours: Look back this many hours (default: 24)
        limit: Maximum alerts to return (default: 20)
    """
    logger.info(f"Fetching alerts: severity={severity}, host={hostname}, hours={hours}")
    return get_zabbix_alerts(severity=severity, hostname=hostname, hours=hours, limit=limit)


@mcp.tool()
def get_ecommerce_transactions(
    action: str | None = None,
    customer: str | None = None,
    order_id: str | None = None,
    status: str | None = None,
    hours: int = 24,
    limit: int = 30,
) -> str:
    """Get e-commerce transaction logs from the TCC Shop web application.

    Query purchase events, cart additions, page views, and payment outcomes
    from the e-commerce web app running on Nginx.

    Args:
        action: Filter by action: page_view, add_to_cart, or checkout
        customer: Filter by customer name (e.g., "Ahmad", "Siti")
        order_id: Filter by specific order ID (e.g., "ORD-123456")
        status: Filter by status: success, payment_failed, out_of_stock, or empty_cart
        hours: Look back this many hours (default: 24)
        limit: Maximum entries to return (default: 30)
    """
    logger.info(f"Fetching ecommerce logs: action={action}, customer={customer}, status={status}")
    return get_ecommerce_logs(action=action, customer=customer, order_id=order_id,
                              status=status, hours=hours, limit=limit)


@mcp.tool()
def get_system_health_summary() -> str:
    """Get an overall health summary of all monitored systems including e-commerce.

    Returns a comprehensive health check by analyzing recent logs and alerts
    across all hosts, services, and e-commerce transaction health.
    """
    logger.info("Generating system health summary")

    # Get recent critical/error alerts
    critical_alerts = get_zabbix_alerts(severity="CRITICAL", hours=6)
    error_alerts = get_zabbix_alerts(severity="ERROR", hours=6)

    # Get recent ecommerce failures
    ecommerce_failures = get_ecommerce_logs(status="payment_failed", hours=6)

    combined_data = (
        f"Critical Alerts (last 6h):\n{critical_alerts}\n\n"
        f"Error Alerts (last 6h):\n{error_alerts}\n\n"
        f"E-Commerce Payment Failures (last 6h):\n{ecommerce_failures}"
    )

    return analyze_logs(
        "Provide a comprehensive health summary of all monitored systems "
        "including the e-commerce web application. Include infrastructure health, "
        "e-commerce transaction success rate, and any payment failures. "
        "Highlight critical issues, trends, and recommended actions.",
        combined_data,
    )


if __name__ == "__main__":
    logger.info("Starting TCC Log Analytics MCP Server")
    mcp.run(transport="streamable-http")
