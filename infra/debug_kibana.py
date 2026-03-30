#!/usr/bin/env python3
"""Debug Kibana visualizations - check their index references"""
import urllib.request, json

KIBANA = 'http://20.212.108.211:5601'

# Check a visualization's full details
vis_ids = ['tcc-log-severity', 'tcc-logs-by-host']
for vid in vis_ids:
    try:
        req = urllib.request.Request(
            f'{KIBANA}/api/saved_objects/visualization/{vid}',
            headers={'kbn-xsrf': 'true'}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read())
        print(f"\n=== {vid} ===")
        attrs = d.get('attributes', {})
        meta = attrs.get('kibanaSavedObjectMeta', {})
        search_src = meta.get('searchSourceJSON', '{}')
        print(f"  searchSourceJSON: {search_src}")
        refs = d.get('references', [])
        print(f"  references: {json.dumps(refs, indent=4)}")
    except Exception as e:
        print(f"  Error: {e}")

# Also check the dashboard references
print("\n=== Dashboard ===")
try:
    req = urllib.request.Request(
        f'{KIBANA}/api/saved_objects/dashboard/tcc-infra-dashboard',
        headers={'kbn-xsrf': 'true'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    d = json.loads(resp.read())
    refs = d.get('references', [])
    print(f"  references: {json.dumps(refs, indent=4)}")
except Exception as e:
    print(f"  Error: {e}")
