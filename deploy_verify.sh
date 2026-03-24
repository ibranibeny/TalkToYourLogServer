#!/bin/bash
# Deployment verification and completion script
VM="tccadmin@4.193.97.88"
SSH="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 $VM"

echo "========================================="
echo "STEP 1: Verifying file deployment"
echo "========================================="

CHECK1=$($SSH "grep -c 'semantic_configuration_name' /opt/tcc/backend/tools/search_logs.py 2>/dev/null" 2>/dev/null || echo "0")
echo "CHECK1 (search_logs.py semantic_configuration_name, expect 0): $CHECK1"

CHECK2=$($SSH "grep -c 'if AZURE_OPENAI_KEY' /opt/tcc/backend/tools/analyze_logs.py 2>/dev/null" 2>/dev/null || echo "0")
echo "CHECK2 (analyze_logs.py if AZURE_OPENAI_KEY, expect 0): $CHECK2"

CHECK3=$($SSH "grep -c 'parse_sse_json' /opt/tcc/frontend/app.py 2>/dev/null" 2>/dev/null || echo "0")
echo "CHECK3 (frontend/app.py parse_sse_json, expect >0): $CHECK3"

NEED_COPY=0
if [ "$CHECK1" != "0" ] || [ "$CHECK2" != "0" ] || [ "$CHECK3" = "0" ]; then
    NEED_COPY=1
fi

echo ""
echo "========================================="
echo "STEP 2: Copy files if needed"
echo "========================================="
if [ "$NEED_COPY" = "1" ]; then
    echo "Files NOT correctly deployed. Copying from /tmp..."
    $SSH "sudo cp /tmp/search_logs.py /opt/tcc/backend/tools/search_logs.py && sudo cp /tmp/analyze_logs.py /opt/tcc/backend/tools/analyze_logs.py && sudo cp /tmp/frontend_app.py /opt/tcc/frontend/app.py" 2>&1
    echo "Copy result: $?"
else
    echo "All files already correctly deployed. Skipping copy."
fi

echo ""
echo "========================================="
echo "STEP 3: Check and clear AZURE_OPENAI_KEY in .env"
echo "========================================="
ENV_LINE=$($SSH "grep 'AZURE_OPENAI_KEY' /opt/tcc/.env 2>/dev/null" 2>/dev/null || echo "NOT_FOUND")
echo "Current .env line: $ENV_LINE"

if echo "$ENV_LINE" | grep -qP 'AZURE_OPENAI_KEY=.+'; then
    echo "Key has a value. Clearing it..."
    $SSH "sudo sed -i 's/^AZURE_OPENAI_KEY=.*/AZURE_OPENAI_KEY=/' /opt/tcc/.env" 2>&1
    echo "Clear result: $?"
    ENV_AFTER=$($SSH "grep 'AZURE_OPENAI_KEY' /opt/tcc/.env 2>/dev/null" 2>/dev/null)
    echo "After clearing: $ENV_AFTER"
else
    echo "Key is already empty or not found. No action needed."
fi

echo ""
echo "========================================="
echo "STEP 4: Restart services"
echo "========================================="
$SSH "sudo systemctl restart mcp-server && sudo systemctl restart streamlit" 2>&1
echo "Restart result: $?"

echo ""
echo "========================================="
echo "STEP 5: Verify services are active"
echo "========================================="
sleep 3
MCP_STATUS=$($SSH "systemctl is-active mcp-server" 2>/dev/null)
STREAMLIT_STATUS=$($SSH "systemctl is-active streamlit" 2>/dev/null)
echo "mcp-server: $MCP_STATUS"
echo "streamlit: $STREAMLIT_STATUS"

echo ""
echo "========================================="
echo "STEP 6: MCP health check"
echo "========================================="
sleep 2
HEALTH=$($SSH "python3 -c \"import urllib.request,json; d=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'t','version':'1'}}}).encode(); r=urllib.request.urlopen(urllib.request.Request('http://localhost:8080/mcp',data=d,headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'})); print('MCP_STATUS:',r.status)\"" 2>&1)
echo "Health check: $HEALTH"

echo ""
echo "========================================="
echo "ALL STEPS COMPLETE"
echo "========================================="
