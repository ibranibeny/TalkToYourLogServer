"""
Elasticsearch to Azure AI Search - Real-time Sync Service

This script continuously polls Elasticsearch for new/updated documents
and pushes them to Azure AI Search with vector embeddings.
"""
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from elasticsearch import Elasticsearch
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from config import (
    ES_URL, ES_INDEX,
    AI_SEARCH_ENDPOINT, AI_SEARCH_KEY, AI_SEARCH_INDEX,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    SYNC_INTERVAL_SECONDS, BATCH_SIZE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_es_client() -> Elasticsearch:
    return Elasticsearch(ES_URL)


def get_search_client() -> SearchClient:
    credential = AzureKeyCredential(AI_SEARCH_KEY)
    return SearchClient(
        endpoint=AI_SEARCH_ENDPOINT,
        index_name=AI_SEARCH_INDEX,
        credential=credential,
    )


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


def generate_embedding(openai_client: AzureOpenAI, text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=text,
        model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    )
    return response.data[0].embedding


def generate_doc_id(doc: dict) -> str:
    raw = json.dumps(doc, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def transform_es_doc_to_search_doc(
    es_doc: dict, openai_client: AzureOpenAI
) -> dict:
    source = es_doc["_source"]
    doc_id = es_doc.get("_id", generate_doc_id(source))

    # Create rich text for embedding
    embedding_text = (
        f"Host: {source.get('hostname', '')} | "
        f"Service: {source.get('service', '')} | "
        f"Severity: {source.get('severity', '')} | "
        f"Category: {source.get('category', '')} | "
        f"Message: {source.get('message', '')}"
    )

    # Add metrics context to embedding if present
    metrics = source.get("metrics", {})
    if metrics:
        metric_parts = []
        if metrics.get("cpu_percent") is not None:
            metric_parts.append(f"CPU: {metrics['cpu_percent']:.1f}%")
        if metrics.get("memory_percent") is not None:
            metric_parts.append(f"Memory: {metrics['memory_percent']:.1f}%")
        if metrics.get("disk_percent") is not None:
            metric_parts.append(f"Disk: {metrics['disk_percent']:.1f}%")
        if metric_parts:
            embedding_text += f" | Metrics: {', '.join(metric_parts)}"

    # Add ecommerce context to embedding if present
    ecommerce = source.get("ecommerce", {})
    if ecommerce:
        embedding_text += (
            f" | Action: {ecommerce.get('action', '')}"
            f" | Order: {ecommerce.get('order_id', '')}"
            f" | Customer: {ecommerce.get('customer', '')}"
            f" | Product: {ecommerce.get('product_name', '')}"
        )

    embedding = generate_embedding(openai_client, embedding_text)

    return {
        "id": doc_id,
        "timestamp": source.get("timestamp"),
        "hostname": source.get("hostname", ""),
        "severity": source.get("severity", ""),
        "service": source.get("service", ""),
        "message": source.get("message", ""),
        "source": source.get("source", ""),
        "category": source.get("category", ""),
        "cpu_percent": metrics.get("cpu_percent"),
        "memory_percent": metrics.get("memory_percent"),
        "disk_percent": metrics.get("disk_percent"),
        "ecommerce_action": ecommerce.get("action"),
        "ecommerce_order_id": ecommerce.get("order_id"),
        "ecommerce_customer": ecommerce.get("customer"),
        "ecommerce_product": ecommerce.get("product_name"),
        "ecommerce_total": ecommerce.get("total"),
        "ecommerce_status": ecommerce.get("status") or ecommerce.get("payment_status"),
        "content_vector": embedding,
    }


def fetch_recent_es_docs(
    es_client: Elasticsearch, since: datetime, batch_size: int = BATCH_SIZE
) -> list[dict]:
    query = {
        "bool": {
            "filter": [
                {"range": {"timestamp": {"gte": since.isoformat()}}}
            ]
        }
    }
    result = es_client.search(
        index=ES_INDEX,
        query=query,
        size=batch_size,
        sort=[{"timestamp": {"order": "asc"}}],
    )
    return result["hits"]["hits"]


def upload_to_ai_search(search_client: SearchClient, documents: list[dict]):
    if not documents:
        return
    result = search_client.upload_documents(documents=documents)
    succeeded = sum(1 for r in result if r.succeeded)
    failed = sum(1 for r in result if not r.succeeded)
    logger.info(f"Uploaded {succeeded} docs, {failed} failures")


def run_sync_loop():
    logger.info("Starting Elasticsearch → Azure AI Search sync service")
    logger.info(f"  ES: {ES_URL}/{ES_INDEX}")
    logger.info(f"  AI Search: {AI_SEARCH_ENDPOINT}/{AI_SEARCH_INDEX}")
    logger.info(f"  Interval: {SYNC_INTERVAL_SECONDS}s | Batch: {BATCH_SIZE}")

    es_client = get_es_client()
    search_client = get_search_client()
    openai_client = get_openai_client()

    # Start syncing from 1 hour ago
    last_sync = datetime.now(timezone.utc) - timedelta(hours=1)

    while True:
        try:
            docs = fetch_recent_es_docs(es_client, since=last_sync)
            if docs:
                logger.info(f"Fetched {len(docs)} new documents from Elasticsearch")
                search_docs = [
                    transform_es_doc_to_search_doc(doc, openai_client)
                    for doc in docs
                ]
                upload_to_ai_search(search_client, search_docs)
                last_sync = datetime.now(timezone.utc)
            else:
                logger.debug("No new documents found")
        except Exception:
            logger.exception("Error during sync cycle")

        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_sync_loop()
