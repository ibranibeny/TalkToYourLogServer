"""
Simple E-Commerce Web Application (Flask + Nginx)
Generates realistic purchase/transaction logs sent to Elasticsearch.
"""
import json
import random
import logging
import os
from datetime import datetime, timezone
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import requests as http_requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Logstash HTTP input endpoint (logs are sent here, then forwarded to Elasticsearch)
LOGSTASH_URL = os.environ.get("LOGSTASH_URL", "http://localhost:5044")

# ─── Product Catalog ──────────────────────────────────────────
PRODUCTS = [
    {"id": "PROD-001", "name": "Wireless Mouse", "price": 25.99, "stock": 150, "category": "electronics"},
    {"id": "PROD-002", "name": "USB-C Hub 7-in-1", "price": 45.50, "stock": 80, "category": "electronics"},
    {"id": "PROD-003", "name": "Mechanical Keyboard", "price": 89.99, "stock": 60, "category": "electronics"},
    {"id": "PROD-004", "name": "Laptop Stand", "price": 35.00, "stock": 200, "category": "accessories"},
    {"id": "PROD-005", "name": "Webcam HD 1080p", "price": 55.00, "stock": 45, "category": "electronics"},
    {"id": "PROD-006", "name": "Monitor Light Bar", "price": 40.00, "stock": 100, "category": "accessories"},
    {"id": "PROD-007", "name": "Ergonomic Chair", "price": 299.99, "stock": 20, "category": "furniture"},
    {"id": "PROD-008", "name": "Standing Desk", "price": 450.00, "stock": 15, "category": "furniture"},
]


def send_log(severity, message, category="ecommerce", extra=None):
    """Send a log entry to Logstash (which forwards to Elasticsearch)."""
    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": "ecommerce-web-01",
        "severity": severity,
        "service": "nginx",
        "message": message,
        "source": "ecommerce-app",
        "category": category,
    }
    if extra:
        doc["ecommerce"] = extra
    doc["metrics"] = {
        "cpu_percent": random.uniform(15, 75),
        "memory_percent": random.uniform(30, 85),
        "disk_percent": random.uniform(20, 60),
        "network_in_bytes": random.randint(5000, 500000),
        "network_out_bytes": random.randint(5000, 500000),
    }
    try:
        http_requests.post(LOGSTASH_URL, json=doc, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send log to Logstash: {e}")


# ─── HTML Templates ───────────────────────────────────────────
SHOP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TCC Shop - Simple E-Commerce</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #f5f5f5; }
        header { background: #2c3e50; color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
        header h1 { font-size: 1.5rem; }
        .cart-badge { background: #e74c3c; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.9rem; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        .products { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; }
        .product-card { background: white; border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: transform 0.2s; }
        .product-card:hover { transform: translateY(-4px); }
        .product-card h3 { margin-bottom: 0.5rem; color: #2c3e50; }
        .product-card .price { font-size: 1.3rem; color: #27ae60; font-weight: bold; margin: 0.5rem 0; }
        .product-card .stock { color: #7f8c8d; font-size: 0.85rem; }
        .product-card .category { background: #3498db; color: white; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; display: inline-block; margin-bottom: 0.5rem; }
        .btn { background: #27ae60; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 5px; cursor: pointer; font-size: 0.95rem; width: 100%; margin-top: 0.5rem; }
        .btn:hover { background: #219a52; }
        .btn-checkout { background: #e74c3c; }
        .btn-checkout:hover { background: #c0392b; }
        .alert { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 1rem; border-radius: 5px; margin-bottom: 1rem; }
        .alert-error { background: #f8d7da; border-color: #f5c6cb; color: #721c24; }
        .cart-section { background: white; border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 2rem; }
        table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        .total { font-size: 1.3rem; font-weight: bold; color: #2c3e50; text-align: right; padding: 1rem 0; }
    </style>
</head>
<body>
    <header>
        <h1>🛒 TCC Shop</h1>
        <span class="cart-badge">Cart: {{ cart_count }} items</span>
    </header>
    <div class="container">
        {% if message %}
        <div class="alert {% if error %}alert-error{% endif %}">{{ message }}</div>
        {% endif %}

        {% if cart %}
        <div class="cart-section">
            <h2>Your Cart</h2>
            <table>
                <tr><th>Product</th><th>Price</th><th>Qty</th><th>Subtotal</th></tr>
                {% for item in cart %}
                <tr>
                    <td>{{ item.name }}</td>
                    <td>${{ "%.2f"|format(item.price) }}</td>
                    <td>{{ item.qty }}</td>
                    <td>${{ "%.2f"|format(item.price * item.qty) }}</td>
                </tr>
                {% endfor %}
            </table>
            <div class="total">Total: ${{ "%.2f"|format(total) }}</div>
            <form method="POST" action="/checkout">
                <input type="text" name="customer_name" placeholder="Your Name" required style="padding:0.5rem;width:60%;margin-right:0.5rem;border:1px solid #ddd;border-radius:4px;">
                <button type="submit" class="btn btn-checkout" style="width:auto;padding:0.6rem 2rem;">Checkout</button>
            </form>
        </div>
        {% endif %}

        <h2 style="margin-bottom:1rem;color:#2c3e50;">Products</h2>
        <div class="products">
            {% for p in products %}
            <div class="product-card">
                <span class="category">{{ p.category }}</span>
                <h3>{{ p.name }}</h3>
                <div class="price">${{ "%.2f"|format(p.price) }}</div>
                <div class="stock">In stock: {{ p.stock }} units</div>
                <form method="POST" action="/add-to-cart">
                    <input type="hidden" name="product_id" value="{{ p.id }}">
                    <button type="submit" class="btn">Add to Cart</button>
                </form>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

ORDER_SUCCESS_HTML = """
<!DOCTYPE html>
<html><head><title>Order Confirmed</title>
<style>
body { font-family: 'Segoe UI', sans-serif; background: #f5f5f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.success { background: white; padding: 3rem; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 500px; }
.success h1 { color: #27ae60; margin-bottom: 1rem; font-size: 2rem; }
.order-id { background: #f8f9fa; padding: 0.5rem 1rem; border-radius: 5px; font-family: monospace; font-size: 1.1rem; }
a { color: #3498db; text-decoration: none; display: inline-block; margin-top: 1.5rem; }
</style></head>
<body>
<div class="success">
    <h1>✅ Order Confirmed!</h1>
    <p>Thank you, <strong>{{ customer }}</strong>!</p>
    <p>Your order ID: <span class="order-id">{{ order_id }}</span></p>
    <p>Total: <strong>${{ "%.2f"|format(total) }}</strong></p>
    <p>{{ item_count }} item(s) purchased</p>
    <a href="/">← Continue Shopping</a>
</div>
</body></html>
"""

# ─── In-memory cart ────────────────────────────────────────────
cart = []


@app.route("/")
def index():
    send_log("INFO", "GET / - Homepage viewed by visitor", "ecommerce",
             {"action": "page_view", "page": "homepage"})
    total = sum(item["price"] * item["qty"] for item in cart)
    return render_template_string(SHOP_HTML, products=PRODUCTS, cart=cart,
                                  cart_count=len(cart), total=total, message=None, error=False)


@app.route("/add-to-cart", methods=["POST"])
def add_to_cart():
    product_id = request.form.get("product_id")
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)

    if not product:
        send_log("ERROR", f"POST /add-to-cart - Product not found: {product_id}", "ecommerce",
                 {"action": "add_to_cart", "status": "error", "product_id": product_id})
        return redirect(url_for("index"))

    # Check stock
    if product["stock"] <= 0:
        send_log("WARNING", f"POST /add-to-cart - Out of stock: {product['name']} ({product_id})", "ecommerce",
                 {"action": "add_to_cart", "status": "out_of_stock", "product_id": product_id, "product_name": product["name"]})
        return redirect(url_for("index"))

    # Add to cart
    existing = next((item for item in cart if item["id"] == product_id), None)
    if existing:
        existing["qty"] += 1
    else:
        cart.append({"id": product_id, "name": product["name"], "price": product["price"], "qty": 1})

    send_log("INFO",
             f"POST /add-to-cart - Added '{product['name']}' (${product['price']}) to cart",
             "ecommerce",
             {"action": "add_to_cart", "status": "success", "product_id": product_id,
              "product_name": product["name"], "price": product["price"]})

    return redirect(url_for("index"))


@app.route("/checkout", methods=["POST"])
def checkout():
    customer_name = request.form.get("customer_name", "Anonymous")

    if not cart:
        send_log("WARNING", f"POST /checkout - Empty cart checkout attempt by {customer_name}", "ecommerce",
                 {"action": "checkout", "status": "empty_cart", "customer": customer_name})
        return redirect(url_for("index"))

    order_id = f"ORD-{random.randint(100000, 999999)}"
    total = sum(item["price"] * item["qty"] for item in cart)
    item_count = sum(item["qty"] for item in cart)
    items = [{"product_id": item["id"], "name": item["name"], "qty": item["qty"], "price": item["price"]} for item in cart]

    # Simulate payment processing
    payment_success = random.random() > 0.1  # 90% success rate

    if payment_success:
        send_log("INFO",
                 f"POST /checkout - Order {order_id} placed by {customer_name}: "
                 f"{item_count} items, total ${total:.2f} - PAYMENT SUCCESS",
                 "ecommerce",
                 {"action": "checkout", "status": "success", "order_id": order_id,
                  "customer": customer_name, "total": total, "item_count": item_count,
                  "items": items, "payment_status": "success"})

        # Update stock
        for item in cart:
            product = next((p for p in PRODUCTS if p["id"] == item["id"]), None)
            if product:
                product["stock"] -= item["qty"]

        cart.clear()
        return render_template_string(ORDER_SUCCESS_HTML, customer=customer_name,
                                      order_id=order_id, total=total, item_count=item_count)
    else:
        send_log("ERROR",
                 f"POST /checkout - Payment FAILED for order {order_id} by {customer_name}: "
                 f"total ${total:.2f} - Gateway timeout",
                 "ecommerce",
                 {"action": "checkout", "status": "payment_failed", "order_id": order_id,
                  "customer": customer_name, "total": total, "error": "gateway_timeout"})
        return redirect(url_for("index"))


@app.route("/health")
def health():
    send_log("INFO", "GET /health - Health check OK", "ecommerce",
             {"action": "health_check", "status": "ok"})
    return jsonify({"status": "ok", "service": "ecommerce-web"})


@app.route("/api/products")
def api_products():
    send_log("INFO", "GET /api/products - API product listing requested", "ecommerce",
             {"action": "api_call", "endpoint": "/api/products"})
    return jsonify(PRODUCTS)


if __name__ == "__main__":
    logger.info("Starting TCC Simple E-Commerce App on port 5000")
    send_log("INFO", "E-Commerce application starting up on ecommerce-web-01", "ecommerce",
             {"action": "app_start", "port": 5000})
    app.run(host="0.0.0.0", port=5000)
