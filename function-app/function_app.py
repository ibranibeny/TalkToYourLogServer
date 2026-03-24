"""
Azure Function: Elasticsearch → Azure AI Search (Vectorization)

Timer-triggered function that polls Elasticsearch for new documents,
generates vector embeddings via Azure OpenAI, and pushes enriched
documents to Azure AI Search.
"""
import json
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone

import azure.functions as func
from elasticsearch import Elasticsearch
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

app = func.FunctionApp()
logger = logging.getLogger(__name__)

# Configuration from App Settings
ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
ES_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "infrastructure-logs")
AI_SEARCH_ENDPOINT = os.environ.get("AI_SEARCH_ENDPOINT", "")
AI_SEARCH_KEY = os.environ.get("AI_SEARCH_KEY", "")
AI_SEARCH_INDEX = os.environ.get("AI_SEARCH_INDEX", "logs-index")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "100"))
SYNC_LOOKBACK_MINUTES = int(os.environ.get("SYNC_LOOKBACK_MINUTES", "10"))


def get_es_client() -> Elasticsearch:
    return Elasticsearch(ES_URL)


def get_search_client() -> SearchClient:
    return SearchClient(
        endpoint=AI_SEARCH_ENDPOINT,
        index_name=AI_SEARCH_INDEX,
        credential=AzureKeyCredential(AI_SEARCH_KEY),
    )


def get_openai_client() -> AzureOpenAI:
    if AZURE_OPENAI_KEY:
        return AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            api_version="2024-06-01",
        )
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


def transform_es_doc(es_doc: dict, openai_client: AzureOpenAI) -> dict:
    """Transform an ES document to AI Search format with vector embedding."""
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
    metrics = source.get("metrics", {})

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


def fetch_recent_docs(es_client: Elasticsearch, since: datetime) -> list[dict]:
    """Fetch documents from ES newer than the given timestamp."""
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
        size=BATCH_SIZE,
        sort=[{"timestamp": {"order": "asc"}}],
    )
    return result["hits"]["hits"]


@app.timer_trigger(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False)
def sync_es_to_ai_search(timer: func.TimerRequest) -> None:
    """Timer-triggered function: polls ES and pushes vectorized docs to AI Search.

    Runs every 5 minutes. Fetches documents from the last SYNC_LOOKBACK_MINUTES
    (default 10 min) to ensure overlap and no missed documents.
    """
    logger.info("Starting ES → AI Search sync cycle")

    if timer.past_due:
        logger.warning("Timer is past due, running catch-up sync")

    try:
        es_client = get_es_client()
        search_client = get_search_client()
        openai_client = get_openai_client()

        since = datetime.now(timezone.utc) - timedelta(minutes=SYNC_LOOKBACK_MINUTES)
        docs = fetch_recent_docs(es_client, since)

        if not docs:
            logger.info("No new documents found in Elasticsearch")
            return

        logger.info(f"Fetched {len(docs)} documents from Elasticsearch")

        # Transform and add embeddings
        search_docs = [transform_es_doc(doc, openai_client) for doc in docs]

        # Upload to AI Search (mergeOrUpload handles deduplication by id)
        result = search_client.upload_documents(documents=search_docs)
        succeeded = sum(1 for r in result if r.succeeded)
        failed = sum(1 for r in result if not r.succeeded)

        logger.info(f"Uploaded to AI Search: {succeeded} succeeded, {failed} failed")

    except Exception:
        logger.exception("Error during ES → AI Search sync")
        raise
