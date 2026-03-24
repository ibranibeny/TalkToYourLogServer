"""
MCP Tool: Query Zabbix Alerts via Elasticsearch

Queries Elasticsearch for Zabbix-sourced alerts and monitoring data.
"""
import json
from elasticsearch import Elasticsearch

from config import ELASTICSEARCH_URL, ELASTICSEARCH_INDEX


def get_es_client() -> Elasticsearch:
    return Elasticsearch(ELASTICSEARCH_URL)


def get_zabbix_alerts(
    severity: str | None = None,
    hostname: str | None = None,
    hours: int = 24,
    limit: int = 20,
) -> str:
    """Query recent Zabbix alerts from Elasticsearch.

    Args:
        severity: Filter by severity level (WARNING, ERROR, CRITICAL)
        hostname: Filter by specific hostname
        hours: How many hours back to look (default: 24)
        limit: Max number of alerts to return (default: 20)
    """
    es = get_es_client()

    must_clauses = [
        {"term": {"source": "zabbix"}},
        {"range": {"timestamp": {"gte": f"now-{hours}h"}}},
    ]

    if severity:
        must_clauses.append({"term": {"severity": severity}})
    if hostname:
        must_clauses.append({"term": {"hostname": hostname}})

    query = {"bool": {"must": must_clauses}}

    result = es.search(
        index=ELASTICSEARCH_INDEX,
        query=query,
        size=limit,
        sort=[{"timestamp": {"order": "desc"}}],
    )

    alerts = []
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        alerts.append({
            "timestamp": src.get("timestamp", ""),
            "hostname": src.get("hostname", ""),
            "severity": src.get("severity", ""),
            "service": src.get("service", ""),
            "message": src.get("message", ""),
            "metrics": src.get("metrics", {}),
        })

    return json.dumps({
        "alerts": alerts,
        "total": result["hits"]["total"]["value"],
        "returned": len(alerts),
    }, indent=2)
