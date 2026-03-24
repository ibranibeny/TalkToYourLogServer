#!/usr/bin/env python3
import urllib.request, json, sys

url = 'http://localhost:8080/mcp'

# Step 1: Initialize
print("=== STEP 1: Initialize ===", flush=True)
init = json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'test','version':'1.0'}}}).encode()
req = urllib.request.Request(url, data=init, headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'})
resp = urllib.request.urlopen(req)
sid = resp.headers.get('Mcp-Session-Id','')
body = resp.read().decode()
print(f'Status: {resp.status}', flush=True)
print(f'Session-Id: {sid}', flush=True)
print(f'Body: {body[:300]}', flush=True)

# Step 2: Notify initialized
print("\n=== STEP 2: Notify initialized ===", flush=True)
notif = json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'}).encode()
req2 = urllib.request.Request(url, data=notif, headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','Mcp-Session-Id':sid})
resp2 = urllib.request.urlopen(req2)
print(f'Status: {resp2.status}', flush=True)

# Step 3: List tools
print("\n=== STEP 3: List tools ===", flush=True)
lt = json.dumps({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}).encode()
req3 = urllib.request.Request(url, data=lt, headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','Mcp-Session-Id':sid})
resp3 = urllib.request.urlopen(req3)
body3 = resp3.read().decode()
print(f'Status: {resp3.status}', flush=True)
# Parse SSE to get tool names
for line in body3.split('\n'):
    if line.startswith('data:'):
        d = json.loads(line[5:].strip())
        if 'result' in d and 'tools' in d['result']:
            tools = d['result']['tools']
            print(f'Tools ({len(tools)}): {[t["name"] for t in tools]}', flush=True)

# Step 4: Call search_logs
print("\n=== STEP 4: Call search_logs ===", flush=True)
call = json.dumps({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'search_logs','arguments':{'query':'critical error','top_k':3}}}).encode()
req4 = urllib.request.Request(url, data=call, headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','Mcp-Session-Id':sid})
try:
    resp4 = urllib.request.urlopen(req4, timeout=30)
    body4 = resp4.read().decode()
    print(f'Status: {resp4.status}', flush=True)
    print(f'Result: {body4[:500]}', flush=True)
except Exception as e:
    print(f'ERROR: {e}', flush=True)
    import traceback
    traceback.print_exc()

print("\n=== DONE ===", flush=True)
