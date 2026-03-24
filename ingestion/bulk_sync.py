"""
One-time bulk sync: Elasticsearch → Azure AI Search (with embeddings).

Reads ALL documents from ES, generates embeddings via Azure OpenAI,
and uploads them to AI Search. Uses DefaultAzureCredential for OpenAI.
Run on the Streamlit VM where the managed identity is already set up.

Usage:
    source /opt/tcc/.env
    python3 bulk_sync.py
"""
import json
import hashlib
import logging
import os
import sys
import time

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
ES_INDEX = os.environ.get("ELASTICSEARCH_INDEX", "infrastructure-logs")
AI_SEARCH_ENDPOINT = os.environ.get("AI_SEARCH_ENDPOINT", "")
AI_SEARCH_KEY = os.environ.get("AI_SEARCH_KEY", "")
AI_SEARCH_INDEX = os.environ.get("AI_SEARCH_INDEX", "logs-index")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
BATCH_SIZE = 50


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


def generate_embedding(client: AzureOpenAI, text: str) -> list[float]:
    resp = client.embeddings.create(input=text, model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
    return resp.data[0].embedding


def transform_doc(hit: dict, openai_client: AzureOpenAI) -> dict:
    source = hit["_source"]
    doc_id = hashlib.sha256(json.dumps(source, sort_keys=True, default=str).encode()).hexdigest()[:32]

    text = (
        f"Host: {source.get('hostname', '')} | "
        f"Service: {source.get('service', '')} | "
        f"Severity: {source.get('severity', '')} | "
        f"Category: {source.get('category', '')} | "
        f"Message: {source.get('message', '')}"
    )
    ecommerce = source.get("ecommerce", {})
    if ecommerce:
        text += (
            f" | Action: {ecommerce.get('action', '')}"
            f" | Order: {ecommerce.get('order_id', '')}"
            f" | Customer: {ecommerce.get('customer', '')}"
            f" | Product: {ecommerce.get('product_name', '')}"
        )

    embedding = generate_embedding(openai_client, text)
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


def fetch_all_docs(es: Elasticsearch) -> list[dict]:
    """Fetch all documents using scroll API."""
    all_hits = []
    resp = es.search(index=ES_INDEX, query={"match_all": {}}, size=BATCH_SIZE, scroll="2m",
                     sort=[{"timestamp": {"order": "asc"}}])
    scroll_id = resp["_scroll_id"]
    all_hits.extend(resp["hits"]["hits"])
    while True:
        resp = es.scroll(scroll_id=scroll_id, scroll="2m")
        if not resp["hits"]["hits"]:
            break
        all_hits.extend(resp["hits"]["hits"])
    es.clear_scroll(scroll_id=scroll_id)
    return all_hits


def main():
    logger.info("Starting bulk sync: Elasticsearch → AI Search")
    logger.info(f"ES: {ES_URL}/{ES_INDEX}")
    logger.info(f"AI Search: {AI_SEARCH_ENDPOINT}/{AI_SEARCH_INDEX}")
    logger.info(f"OpenAI: {AZURE_OPENAI_ENDPOINT}")

    es = Elasticsearch(ES_URL)
    search_client = SearchClient(
        endpoint=AI_SEARCH_ENDPOINT,
        index_name=AI_SEARCH_INDEX,
        credential=AzureKeyCredential(AI_SEARCH_KEY),
    )
    openai_client = get_openai_client()

    # Fetch all docs
    logger.info("Fetching all documents from Elasticsearch...")
    hits = fetch_all_docs(es)
    logger.info(f"Found {len(hits)} documents")

    if not hits:
        logger.info("No documents to sync")
        return

    # Process in batches
    total_ok = 0
    total_fail = 0
    for i in range(0, len(hits), BATCH_SIZE):
        batch = hits[i : i + BATCH_SIZE]
        logger.info(f"Processing batch {i // BATCH_SIZE + 1} ({len(batch)} docs)...")

        search_docs = []
        for hit in batch:
            try:
                doc = transform_doc(hit, openai_client)
                search_docs.append(doc)
            except Exception as e:
                logger.error(f"Failed to transform doc: {e}")
                total_fail += 1

        if search_docs:
            result = search_client.upload_documents(documents=search_docs)
            ok = sum(1 for r in result if r.succeeded)
            fail = sum(1 for r in result if not r.succeeded)
            total_ok += ok
            total_fail += fail
            logger.info(f"  Uploaded: {ok} succeeded, {fail} failed")

        # Rate limit protection
        time.sleep(1)

    logger.info(f"Bulk sync complete: {total_ok} succeeded, {total_fail} failed")


if __name__ == "__main__":
    main()
