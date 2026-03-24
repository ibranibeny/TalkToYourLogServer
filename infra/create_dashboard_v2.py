#!/usr/bin/env python3
"""Create Kibana dashboard with legacy visualizations (not Lens) for compatibility."""
import urllib.request
import json
import sys

KIBANA = "http://4.193.105.195:5601"
DV_ID = "14a7907b-d2d5-4943-998d-11ec401db04d"

def api_call(method, path, body=None):
    url = f"{KIBANA}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers={
        "kbn-xsrf": "true", "Content-Type": "application/json"
    }, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:300]
        if e.code == 409:
            # Already exists, update instead
            req2 = urllib.request.Request(url, data=data, headers={
                "kbn-xsrf": "true", "Content-Type": "application/json"
            }, method="PUT")
            resp2 = urllib.request.urlopen(req2, timeout=15)
            return json.loads(resp2.read())
        print(f"  HTTP {e.code}: {err}")
        return None

def create_vis(vis_id, title, vis_type, aggs, params=None):
    if params is None:
        params = {}
    base_params = {"addTooltip": True, "addLegend": True}
    base_params.update(params)
    
    body = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": vis_type,
                "aggs": aggs,
                "params": base_params
            }),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "index": DV_ID,
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": [
            {"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": DV_ID}
        ]
    }
    
    result = api_call("POST", f"/api/saved_objects/visualization/{vis_id}", body)
    if result:
        print(f"  OK: {title} ({result.get('id', vis_id)})")
    return result

print("=== Creating Visualizations ===")

# 1. Log Volume Over Time (area chart)
create_vis("tcc-log-volume", "Log Volume Over Time", "area", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "date_histogram", "params": {
        "field": "timestamp", "interval": "auto", "min_doc_count": 1
    }, "schema": "segment"}
])

# 2. Severity Distribution (pie/donut)
create_vis("tcc-severity", "Severity Distribution", "pie", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms", "params": {
        "field": "severity", "size": 10, "order": "desc", "orderBy": "1"
    }, "schema": "segment"}
], {"isDonut": True})

# 3. Infrastructure vs E-Commerce (pie)
create_vis("tcc-category", "Infrastructure vs E-Commerce", "pie", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms", "params": {
        "field": "category", "size": 5, "order": "desc", "orderBy": "1"
    }, "schema": "segment"}
])

# 4. Top Services (horizontal bar)
create_vis("tcc-services", "Top Services by Log Count", "horizontal_bar", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms", "params": {
        "field": "service", "size": 10, "order": "desc", "orderBy": "1"
    }, "schema": "segment"}
])

# 5. Logs by Hostname (bar)
create_vis("tcc-hostnames", "Logs by Hostname", "histogram", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms", "params": {
        "field": "hostname", "size": 10, "order": "desc", "orderBy": "1"
    }, "schema": "segment"}
])

# 6. CPU & Memory Over Time (line)
create_vis("tcc-cpu-mem", "CPU & Memory Usage Over Time", "line", [
    {"id": "1", "enabled": True, "type": "avg", "params": {"field": "metrics.cpu_percent"}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "avg", "params": {"field": "metrics.memory_percent"}, "schema": "metric"},
    {"id": "3", "enabled": True, "type": "date_histogram", "params": {
        "field": "timestamp", "interval": "auto", "min_doc_count": 1
    }, "schema": "segment"}
])

# 7. E-Commerce Actions (bar)
create_vis("tcc-ecom-actions", "E-Commerce Actions", "histogram", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms", "params": {
        "field": "ecommerce.action", "size": 10, "order": "desc", "orderBy": "1"
    }, "schema": "segment"}
])

# 8. Top Products (horizontal bar)
create_vis("tcc-top-products", "Top E-Commerce Products", "horizontal_bar", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms", "params": {
        "field": "ecommerce.product_name", "size": 10, "order": "desc", "orderBy": "1"
    }, "schema": "segment"}
])

# 9. Payment Status (donut)
create_vis("tcc-payment", "Payment Status", "pie", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms", "params": {
        "field": "ecommerce.payment_status", "size": 10, "order": "desc", "orderBy": "1"
    }, "schema": "segment"}
], {"isDonut": True})

# 10. Order Status (donut)
create_vis("tcc-order-status", "E-Commerce Order Status", "pie", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"},
    {"id": "2", "enabled": True, "type": "terms", "params": {
        "field": "ecommerce.status", "size": 10, "order": "desc", "orderBy": "1"
    }, "schema": "segment"}
], {"isDonut": True})

# 11. Total log count metric
create_vis("tcc-total-logs", "Total Log Count", "metric", [
    {"id": "1", "enabled": True, "type": "count", "params": {}, "schema": "metric"}
], {"metric": {"percentageMode": False, "style": {"fontSize": 60}}})

print("\n=== Creating Dashboard ===")

vis_ids = [
    "tcc-total-logs", "tcc-log-volume", "tcc-severity", "tcc-category",
    "tcc-services", "tcc-hostnames", "tcc-cpu-mem", "tcc-ecom-actions",
    "tcc-top-products", "tcc-payment", "tcc-order-status"
]

# Grid layout: 48 columns wide
grid_layout = [
    # (vis_id, x, y, w, h)
    ("tcc-total-logs",   0,  0, 12, 8),
    ("tcc-severity",    12,  0, 12, 8),
    ("tcc-category",    24,  0, 12, 8),
    ("tcc-payment",     36,  0, 12, 8),
    ("tcc-log-volume",   0,  8, 24, 12),
    ("tcc-cpu-mem",     24,  8, 24, 12),
    ("tcc-services",     0, 20, 24, 12),
    ("tcc-hostnames",   24, 20, 24, 12),
    ("tcc-ecom-actions", 0, 32, 16, 12),
    ("tcc-top-products",16, 32, 16, 12),
    ("tcc-order-status",32, 32, 16, 12),
]

panels = []
refs = []
for i, (vid, x, y, w, h) in enumerate(grid_layout):
    panels.append({
        "version": "8.19.0",
        "type": "visualization",
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)},
        "panelIndex": str(i),
        "embeddableConfig": {},
        "panelRefName": f"panel_{i}"
    })
    refs.append({
        "name": f"panel_{i}",
        "type": "visualization",
        "id": vid
    })

dashboard_body = {
    "attributes": {
        "title": "TCC PoC - Infrastructure & E-Commerce Monitoring",
        "description": "Real-time monitoring dashboard for TCC PoC: infrastructure logs, system metrics, and e-commerce activity",
        "panelsJSON": json.dumps(panels),
        "timeRestore": True,
        "timeTo": "now",
        "timeFrom": "now-7d",
        "refreshInterval": {"pause": False, "value": 30000},
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": []
            })
        }
    },
    "references": refs
}

result = api_call("POST", "/api/saved_objects/dashboard/tcc-poc-dashboard", dashboard_body)
if result:
    print(f"  OK: Dashboard created ({result.get('id', 'tcc-poc-dashboard')})")
else:
    print("  FAILED to create dashboard")

print(f"\nDashboard URL: {KIBANA}/app/dashboards#/view/tcc-poc-dashboard")
