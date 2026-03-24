"""
MCP Tool: Query E-Commerce Logs

Queries Elasticsearch for e-commerce transaction logs including
purchases, cart actions, and payment events.
"""
import json
from elasticsearch import Elasticsearch

from config import ELASTICSEARCH_URL, ELASTICSEARCH_INDEX


def get_es_client() -> Elasticsearch:
    return Elasticsearch(ELASTICSEARCH_URL)


def get_ecommerce_logs(
    action: str | None = None,
    customer: str | None = None,
    order_id: str | None = None,
    status: str | None = None,
    hours: int = 24,
    limit: int = 30,
) -> str:
    """Query e-commerce transaction logs from Elasticsearch.

    Args:
        action: Filter by action type (page_view, add_to_cart, checkout)
        customer: Filter by customer name
        order_id: Filter by specific order ID
        status: Filter by status (success, payment_failed, out_of_stock, empty_cart)
        hours: How many hours back to look (default: 24)
        limit: Max number of entries to return (default: 30)
    """
    es = get_es_client()

    must_clauses = [
        {"term": {"category": "ecommerce"}},
        {"range": {"timestamp": {"gte": f"now-{hours}h"}}},
    ]

    if action:
        must_clauses.append({"term": {"ecommerce.action": action}})
    if customer:
        must_clauses.append({"term": {"ecommerce.customer": customer}})
    if order_id:
        must_clauses.append({"term": {"ecommerce.order_id": order_id}})
    if status:
        must_clauses.append({"term": {"ecommerce.status": status}})

    query = {"bool": {"must": must_clauses}}

    result = es.search(
        index=ELASTICSEARCH_INDEX,
        query=query,
        size=limit,
        sort=[{"timestamp": {"order": "desc"}}],
    )

    entries = []
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        entry = {
            "timestamp": src.get("timestamp", ""),
            "severity": src.get("severity", ""),
            "message": src.get("message", ""),
        }
        ecom = src.get("ecommerce", {})
        if ecom:
            entry["ecommerce"] = {
                "action": ecom.get("action"),
                "order_id": ecom.get("order_id"),
                "customer": ecom.get("customer"),
                "product_name": ecom.get("product_name"),
                "price": ecom.get("price"),
                "total": ecom.get("total"),
                "item_count": ecom.get("item_count"),
                "status": ecom.get("status"),
                "payment_status": ecom.get("payment_status"),
            }
        entries.append(entry)

    return json.dumps({
        "entries": entries,
        "total": result["hits"]["total"]["value"],
        "returned": len(entries),
    }, indent=2)
