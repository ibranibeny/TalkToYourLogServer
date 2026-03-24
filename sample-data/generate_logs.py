"""
Generate sample infrastructure and e-commerce log data for testing.
Produces logs that simulate Zabbix-monitored infrastructure + e-commerce transactions.
"""
import json
import random
from datetime import datetime, timedelta, timezone


HOSTNAMES = [
    "ecommerce-web-01",
    "db-server-01", "db-server-02",
    "app-server-01", "app-server-02",
    "monitor-01", "cache-server-01",
]

SERVICES = ["nginx", "mysql", "postgresql", "redis", "docker", "sshd", "cron", "zabbix-agent", "gunicorn", "logstash"]

SEVERITIES = ["INFO", "WARNING", "ERROR", "CRITICAL"]
SEVERITY_WEIGHTS = [50, 30, 15, 5]

MESSAGES = {
    "INFO": [
        "Service {service} is running normally on {host}",
        "Scheduled backup completed successfully on {host}",
        "Health check passed for {service} on {host}",
        "Log rotation completed on {host}",
        "Connection pool refreshed for {service} on {host}",
    ],
    "WARNING": [
        "High memory usage detected on {host}: {mem}%",
        "CPU load average elevated on {host}: {cpu}%",
        "Disk usage approaching threshold on {host}: {disk}%",
        "Slow query detected in {service} on {host}: 2.3s",
        "Connection timeout for {service} on {host}",
    ],
    "ERROR": [
        "Service {service} restart required on {host}",
        "Failed to connect to {service} on {host}: connection refused",
        "Out of memory error in {service} on {host}",
        "Disk write error on {host}: I/O error",
        "Authentication failure for {service} on {host}",
    ],
    "CRITICAL": [
        "Service {service} DOWN on {host} - immediate action required",
        "Host {host} unreachable - all services affected",
        "Database replication lag critical on {host}: 300s",
        "Disk space critically low on {host}: {disk}% used",
        "Security breach detected on {host}: unauthorized access attempt",
    ],
}


def generate_log_entry(base_time: datetime) -> dict:
    severity = random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0]
    host = random.choice(HOSTNAMES)
    service = random.choice(SERVICES)
    cpu = random.randint(10, 99)
    mem = random.randint(20, 95)
    disk = random.randint(15, 95)

    message_template = random.choice(MESSAGES[severity])
    message = message_template.format(
        service=service, host=host, cpu=cpu, mem=mem, disk=disk
    )

    timestamp = base_time + timedelta(seconds=random.randint(0, 3600))

    return {
        "timestamp": timestamp.isoformat(),
        "hostname": host,
        "severity": severity,
        "service": service,
        "message": message,
        "source": "zabbix",
        "category": "infrastructure",
        "metrics": {
            "cpu_percent": float(cpu),
            "memory_percent": float(mem),
            "disk_percent": float(disk),
            "network_in_bytes": random.randint(1000, 9999999),
            "network_out_bytes": random.randint(1000, 9999999),
        },
    }


# ─── E-Commerce Data ──────────────────────────────────────────
ECOM_PRODUCTS = [
    {"id": "PROD-001", "name": "Wireless Mouse", "price": 25.99},
    {"id": "PROD-002", "name": "USB-C Hub 7-in-1", "price": 45.50},
    {"id": "PROD-003", "name": "Mechanical Keyboard", "price": 89.99},
    {"id": "PROD-004", "name": "Laptop Stand", "price": 35.00},
    {"id": "PROD-005", "name": "Webcam HD 1080p", "price": 55.00},
    {"id": "PROD-006", "name": "Monitor Light Bar", "price": 40.00},
    {"id": "PROD-007", "name": "Ergonomic Chair", "price": 299.99},
    {"id": "PROD-008", "name": "Standing Desk", "price": 450.00},
]

CUSTOMERS = ["Ahmad", "Siti", "Budi", "Dewi", "Rina", "Farid", "Lina", "Hasan", "Mega", "Yusuf"]

ECOM_ACTIONS = ["page_view", "page_view", "add_to_cart", "add_to_cart", "checkout"]


def generate_ecommerce_entry(base_time: datetime) -> dict:
    action = random.choice(ECOM_ACTIONS)
    product = random.choice(ECOM_PRODUCTS)
    customer = random.choice(CUSTOMERS)
    timestamp = base_time + timedelta(seconds=random.randint(0, 3600))

    ecommerce = {"action": action, "customer": customer}

    if action == "page_view":
        severity = "INFO"
        message = f"GET / - Homepage viewed by {customer}"
        ecommerce["page"] = "homepage"
    elif action == "add_to_cart":
        severity = "INFO"
        message = f"POST /add-to-cart - Added '{product['name']}' (${product['price']}) to cart by {customer}"
        ecommerce.update({
            "product_id": product["id"],
            "product_name": product["name"],
            "price": product["price"],
            "status": "success",
        })
    else:  # checkout
        order_id = f"ORD-{random.randint(100000, 999999)}"
        qty = random.randint(1, 3)
        total = round(product["price"] * qty, 2)
        payment_ok = random.random() > 0.15  # 85% success
        if payment_ok:
            severity = "INFO"
            message = f"POST /checkout - Order {order_id} by {customer}: {qty} items, total ${total} - PAYMENT SUCCESS"
            ecommerce.update({
                "order_id": order_id, "total": total, "item_count": qty,
                "product_id": product["id"], "product_name": product["name"],
                "status": "success", "payment_status": "success",
            })
        else:
            severity = "ERROR"
            message = f"POST /checkout - Payment FAILED for {order_id} by {customer}: ${total} - Gateway timeout"
            ecommerce.update({
                "order_id": order_id, "total": total, "item_count": qty,
                "product_id": product["id"], "product_name": product["name"],
                "status": "payment_failed", "payment_status": "payment_failed",
                "error": "gateway_timeout",
            })

    return {
        "timestamp": timestamp.isoformat(),
        "hostname": "ecommerce-web-01",
        "severity": severity,
        "service": "nginx",
        "message": message,
        "source": "ecommerce-app",
        "category": "ecommerce",
        "ecommerce": ecommerce,
        "metrics": {
            "cpu_percent": round(random.uniform(15, 75), 1),
            "memory_percent": round(random.uniform(30, 85), 1),
            "disk_percent": round(random.uniform(20, 60), 1),
            "network_in_bytes": random.randint(5000, 500000),
            "network_out_bytes": random.randint(5000, 500000),
        },
    }


def generate_logs(count: int = 200, hours_back: int = 24) -> list[dict]:
    now = datetime.now(timezone.utc)
    logs = []
    # Infrastructure logs
    for i in range(count):
        base_time = now - timedelta(hours=random.uniform(0, hours_back))
        logs.append(generate_log_entry(base_time))
    # E-commerce transaction logs
    for i in range(count // 2):
        base_time = now - timedelta(hours=random.uniform(0, hours_back))
        logs.append(generate_ecommerce_entry(base_time))
    logs.sort(key=lambda x: x["timestamp"])
    return logs


if __name__ == "__main__":
    logs = generate_logs(200)
    output_file = "sample_logs.json"
    with open(output_file, "w") as f:
        json.dump(logs, f, indent=2)
    print(f"Generated {len(logs)} sample log entries → {output_file}")

    # Print summary
    from collections import Counter
    severities = Counter(log["severity"] for log in logs)
    hosts = Counter(log["hostname"] for log in logs)
    categories = Counter(log["category"] for log in logs)
    ecom_actions = Counter(
        log.get("ecommerce", {}).get("action", "N/A")
        for log in logs if log.get("category") == "ecommerce"
    )
    print(f"\nSeverity distribution: {dict(severities)}")
    print(f"Host distribution: {dict(hosts)}")
    print(f"Category distribution: {dict(categories)}")
    print(f"E-Commerce actions: {dict(ecom_actions)}")
