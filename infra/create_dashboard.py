#!/usr/bin/env python3
"""Create Kibana dashboard for TCC PoC via saved_objects API"""
import json
import os
import sys
import tempfile
import subprocess

KIBANA = "http://4.193.105.195:5601"
DV_ID = "14a7907b-d2d5-4943-998d-11ec401db04d"

def mk(vid, title, vt, cols, vc):
    cm, co = {}, []
    for c in cols:
        co.append(c["id"])
        cm[c["id"]] = c["d"]
    st = {
        "datasourceStates": {
            "formBased": {
                "layers": {
                    "layer1": {
                        "columns": cm,
                        "columnOrder": co,
                        "incompleteColumns": {}
                    }
                }
            }
        },
        "visualization": vc,
        "query": {"query": "", "language": "kuery"},
        "filters": []
    }
    return {
        "id": vid,
        "type": "lens",
        "attributes": {
            "title": title,
            "visualizationType": vt,
            "state": json.dumps(st),
            "references": [
                {"type": "index-pattern", "id": DV_ID, "name": "indexpattern-datasource-layer-layer1"}
            ]
        },
        "references": [
            {"type": "index-pattern", "id": DV_ID, "name": "indexpattern-datasource-layer-layer1"}
        ]
    }


def main():
    objects = []

    vis_defs = [
        ("vis-lv", "Log Volume Over Time", "lnsXY",
         [{"id": "ts", "d": {"operationType": "date_histogram", "sourceField": "timestamp", "isBucketed": True, "scale": "interval", "params": {"interval": "auto"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Log Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "accessors": ["cnt"], "xAccessor": "ts", "seriesType": "area"}], "preferredSeriesType": "area"}),

        ("vis-sev", "Severity Distribution", "lnsPie",
         [{"id": "sev", "d": {"operationType": "terms", "sourceField": "severity", "isBucketed": True, "params": {"size": 5, "orderBy": {"type": "column", "columnId": "cnt"}, "orderDirection": "desc"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "primaryGroups": ["sev"], "metrics": ["cnt"]}], "shape": "donut"}),

        ("vis-cat", "Infrastructure vs E-Commerce", "lnsPie",
         [{"id": "cat", "d": {"operationType": "terms", "sourceField": "category", "isBucketed": True, "params": {"size": 5, "orderBy": {"type": "column", "columnId": "cnt"}, "orderDirection": "desc"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "primaryGroups": ["cat"], "metrics": ["cnt"]}], "shape": "pie"}),

        ("vis-svc", "Top Services", "lnsXY",
         [{"id": "svc", "d": {"operationType": "terms", "sourceField": "service", "isBucketed": True, "params": {"size": 10, "orderBy": {"type": "column", "columnId": "cnt"}, "orderDirection": "desc"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "accessors": ["cnt"], "xAccessor": "svc", "seriesType": "bar_horizontal"}], "preferredSeriesType": "bar_horizontal"}),

        ("vis-host", "Logs by Hostname", "lnsXY",
         [{"id": "host", "d": {"operationType": "terms", "sourceField": "hostname", "isBucketed": True, "params": {"size": 10, "orderBy": {"type": "column", "columnId": "cnt"}, "orderDirection": "desc"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "accessors": ["cnt"], "xAccessor": "host", "seriesType": "bar"}], "preferredSeriesType": "bar"}),

        ("vis-cpu", "CPU & Memory Usage", "lnsXY",
         [{"id": "ts", "d": {"operationType": "date_histogram", "sourceField": "timestamp", "isBucketed": True, "scale": "interval", "params": {"interval": "auto"}}},
          {"id": "cpu", "d": {"operationType": "average", "sourceField": "metrics.cpu_percent", "isBucketed": False, "label": "Avg CPU %"}},
          {"id": "mem", "d": {"operationType": "average", "sourceField": "metrics.memory_percent", "isBucketed": False, "label": "Avg Memory %"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "accessors": ["cpu", "mem"], "xAccessor": "ts", "seriesType": "line"}], "preferredSeriesType": "line"}),

        ("vis-act", "E-Commerce Actions", "lnsXY",
         [{"id": "act", "d": {"operationType": "terms", "sourceField": "ecommerce.action", "isBucketed": True, "params": {"size": 10, "orderBy": {"type": "column", "columnId": "cnt"}, "orderDirection": "desc"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "accessors": ["cnt"], "xAccessor": "act", "seriesType": "bar"}], "preferredSeriesType": "bar"}),

        ("vis-prod", "Top Products", "lnsXY",
         [{"id": "prod", "d": {"operationType": "terms", "sourceField": "ecommerce.product_name", "isBucketed": True, "params": {"size": 10, "orderBy": {"type": "column", "columnId": "cnt"}, "orderDirection": "desc"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "accessors": ["cnt"], "xAccessor": "prod", "seriesType": "bar_horizontal"}], "preferredSeriesType": "bar_horizontal"}),

        ("vis-pay", "Payment Status", "lnsPie",
         [{"id": "pay", "d": {"operationType": "terms", "sourceField": "ecommerce.payment_status", "isBucketed": True, "params": {"size": 5, "orderBy": {"type": "column", "columnId": "cnt"}, "orderDirection": "desc"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "primaryGroups": ["pay"], "metrics": ["cnt"]}], "shape": "donut"}),

        ("vis-ord", "Order Status", "lnsPie",
         [{"id": "st", "d": {"operationType": "terms", "sourceField": "ecommerce.status", "isBucketed": True, "params": {"size": 5, "orderBy": {"type": "column", "columnId": "cnt"}, "orderDirection": "desc"}}},
          {"id": "cnt", "d": {"operationType": "count", "isBucketed": False, "label": "Count"}}],
         {"layers": [{"layerId": "layer1", "layerType": "data", "primaryGroups": ["st"], "metrics": ["cnt"]}], "shape": "donut"}),
    ]

    for args in vis_defs:
        objects.append(mk(*args))

    # Dashboard
    grid = [
        ("vis-lv", 0, 0, 24, 12),
        ("vis-sev", 24, 0, 12, 12),
        ("vis-cat", 36, 0, 12, 12),
        ("vis-svc", 0, 12, 24, 12),
        ("vis-host", 24, 12, 24, 12),
        ("vis-cpu", 0, 24, 24, 12),
        ("vis-act", 24, 24, 24, 12),
        ("vis-prod", 0, 36, 24, 12),
        ("vis-pay", 24, 36, 12, 12),
        ("vis-ord", 36, 36, 12, 12),
    ]

    panels = []
    for i, (vid, x, y, w, h) in enumerate(grid):
        panels.append({
            "version": "8.19.0",
            "type": "lens",
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": f"p{i}"},
            "panelIndex": f"p{i}",
            "panelRefName": f"panel_{i}",
            "embeddableConfig": {}
        })

    refs = [{"name": f"panel_{i}", "type": "lens", "id": vid} for i, (vid, *_) in enumerate(grid)]
    refs.append({"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": DV_ID})

    objects.append({
        "id": "tcc-poc-dashboard",
        "type": "dashboard",
        "attributes": {
            "title": "TCC PoC - Infrastructure & E-Commerce Monitoring",
            "description": "Real-time monitoring dashboard for infrastructure logs, system metrics, and e-commerce activity",
            "panelsJSON": json.dumps(panels),
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-24h",
            "refreshInterval": json.dumps({"pause": False, "value": 30000}),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
            }
        },
        "references": refs
    })

    # Write NDJSON
    ndjson_path = "/tmp/dashboard.ndjson"
    with open(ndjson_path, "w") as f:
        for obj in objects:
            f.write(json.dumps(obj) + "\n")

    print(f"Created {ndjson_path} with {len(objects)} objects")

    # Upload via multipart/form-data using urllib
    import io
    boundary = "----KibanaDashboardBoundary"

    with open(ndjson_path, "rb") as f:
        file_data = f.read()

    # Build multipart body
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(b'Content-Disposition: form-data; name="file"; filename="dashboard.ndjson"\r\n')
    body.write(b"Content-Type: application/ndjson\r\n\r\n")
    body.write(file_data)
    body.write(f"\r\n--{boundary}--\r\n".encode())

    import urllib.request
    req = urllib.request.Request(
        f"{KIBANA}/api/saved_objects/_import?overwrite=true",
        data=body.getvalue(),
        headers={
            "kbn-xsrf": "true",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        },
        method="POST"
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        print(f"Success: {result.get('success')}")
        print(f"Objects imported: {result.get('successCount')}")
        if result.get("errors"):
            for err in result["errors"][:5]:
                print(f"  Error: {err.get('id')} - {json.dumps(err.get('error', {}))[:300]}")
        if not result.get("success") and not result.get("errors"):
            print(f"Full response: {json.dumps(result)[:500]}")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode()[:500]}")
    except Exception as e:
        print(f"Error: {e}")

    print(f"\nDashboard URL: {KIBANA}/app/dashboards#/view/tcc-poc-dashboard")


if __name__ == "__main__":
    main()
