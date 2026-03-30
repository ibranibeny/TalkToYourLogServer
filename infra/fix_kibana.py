#!/usr/bin/env python3
"""Fix Kibana index pattern: create with correct ID 'infrastructure-logs'"""
import urllib.request, json, sys

KIBANA = 'http://20.212.108.211:5601'

# 1. Check if index-pattern with ID 'infrastructure-logs' exists
try:
    req = urllib.request.Request(
        f'{KIBANA}/api/saved_objects/index-pattern/infrastructure-logs',
        headers={'kbn-xsrf': 'true'}
    )
    urllib.request.urlopen(req, timeout=10)
    print("Index pattern 'infrastructure-logs' already exists with correct ID")
except urllib.error.HTTPError as e:
    if e.code == 404:
        print("Index pattern with ID 'infrastructure-logs' not found. Creating...")
        data = json.dumps({
            'attributes': {
                'title': 'infrastructure-logs*',
                'timeFieldName': 'timestamp'
            }
        }).encode()
        req = urllib.request.Request(
            f'{KIBANA}/api/saved_objects/index-pattern/infrastructure-logs',
            data=data,
            headers={'kbn-xsrf': 'true', 'Content-Type': 'application/json'},
            method='POST'
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read())
            print(f"Created: id={result.get('id')}")
        except Exception as ex:
            print(f"Create failed: {ex}")
            sys.exit(1)
    else:
        print(f"Unexpected error checking pattern: {e}")
        sys.exit(1)

# 2. Verify
try:
    req = urllib.request.Request(
        f'{KIBANA}/api/saved_objects/index-pattern/infrastructure-logs',
        headers={'kbn-xsrf': 'true'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    d = json.loads(resp.read())
    print(f"Verified: id={d['id']}  title={d['attributes']['title']}")
except Exception as e:
    print(f"Verification failed: {e}")
    sys.exit(1)

print("Done! Refresh the Kibana dashboard to see the visualizations.")
