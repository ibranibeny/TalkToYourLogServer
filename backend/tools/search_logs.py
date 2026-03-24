"""
MCP Tool: Search Logs via Azure AI Search

Provides semantic and keyword search over indexed infrastructure logs.
"""
import json
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from config import (
    AI_SEARCH_ENDPOINT, AI_SEARCH_KEY, AI_SEARCH_INDEX,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
)


def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=AI_SEARCH_ENDPOINT,
        index_name=AI_SEARCH_INDEX,
        credential=AzureKeyCredential(AI_SEARCH_KEY),
    )


def get_embedding(text: str) -> list[float]:
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2024-06-01",
    )
    response = client.embeddings.create(
        input=text,
        model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    )
    return response.data[0].embedding


def search_logs(
    query: str,
    severity: str | None = None,
    hostname: str | None = None,
    service: str | None = None,
    top: int = 10,
    use_vector: bool = True,
) -> str:
    """Search infrastructure logs using semantic and/or vector search.

    Args:
        query: Natural language search query
        severity: Filter by severity (INFO, WARNING, ERROR, CRITICAL)
        hostname: Filter by hostname
        service: Filter by service name
        top: Number of results to return
        use_vector: Whether to use vector search
    """
    client = get_search_client()

    # Build filter
    filters = []
    if severity:
        filters.append(f"severity eq '{severity}'")
    if hostname:
        filters.append(f"hostname eq '{hostname}'")
    if service:
        filters.append(f"service eq '{service}'")
    filter_expr = " and ".join(filters) if filters else None

    search_kwargs = {
        "search_text": query,
        "filter": filter_expr,
        "top": top,
        "select": ["id", "timestamp", "hostname", "severity", "service", "message",
                    "cpu_percent", "memory_percent", "disk_percent",
                    "ecommerce_action", "ecommerce_order_id", "ecommerce_customer",
                    "ecommerce_product", "ecommerce_total", "ecommerce_status"],
        "query_type": "semantic",
        "semantic_configuration_name": "my-semantic-config",
    }

    if use_vector:
        embedding = get_embedding(query)
        vector_query = VectorizedQuery(
            vector=embedding,
            k_nearest_neighbors=top,
            fields="content_vector",
        )
        search_kwargs["vector_queries"] = [vector_query]

    results = client.search(**search_kwargs)

    docs = []
    for result in results:
        doc = {
            "timestamp": str(result.get("timestamp", "")),
            "hostname": result.get("hostname", ""),
            "severity": result.get("severity", ""),
            "service": result.get("service", ""),
            "message": result.get("message", ""),
            "cpu_percent": result.get("cpu_percent"),
            "memory_percent": result.get("memory_percent"),
            "disk_percent": result.get("disk_percent"),
            "score": result.get("@search.score"),
        }
        # Include ecommerce fields if present
        ecom_action = result.get("ecommerce_action")
        if ecom_action:
            doc["ecommerce"] = {
                "action": ecom_action,
                "order_id": result.get("ecommerce_order_id"),
                "customer": result.get("ecommerce_customer"),
                "product": result.get("ecommerce_product"),
                "total": result.get("ecommerce_total"),
                "status": result.get("ecommerce_status"),
            }
        docs.append(doc)

    return json.dumps({"results": docs, "count": len(docs)}, indent=2)
