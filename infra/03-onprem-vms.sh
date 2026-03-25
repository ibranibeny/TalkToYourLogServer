#!/bin/bash
# =============================================================================
# TCC PoC - 03 - On-Prem Simulation VMs (Zabbix + Elasticsearch + E-Commerce)
# Uses cloud-init for package install + az vm run-command for configuration.
#
# ─── Credentials ─────────────────────────────────────────────────────────────
#  VM SSH:            ssh tccadmin@<vm-public-ip>  (key-based auth)
#
#  Zabbix Web UI:     http://<zabbix-ip>/zabbix
#    Login:           Admin / zabbix
#
#  Zabbix MySQL:      Host: localhost | DB: zabbix
#    User:            zabbix
#    Password:        zabbix_poc_pass
#    Auth plugin:     mysql_native_password
#
#  Elasticsearch:     http://<es-ip>:9200  (no auth, xpack.security disabled)
#  Kibana:            http://<es-ip>:5601  (no auth)
#
#  E-Commerce App:    http://<ecommerce-ip>  (Nginx → Gunicorn:5000)
# ─────────────────────────────────────────────────────────────────────────────
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/variables.sh"

# ─── Helper: wait for VM agent to be ready ───────────────────────────────────
wait_for_vm_agent() {
  local vm_name="$1"
  echo "  Waiting for $vm_name agent to be ready..."
  for i in $(seq 1 30); do
    STATE=$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$vm_name" \
      --query "instanceView.vmAgent.statuses[0].code" -o tsv 2>/dev/null || echo "")
    if [[ "$STATE" == "ProvisioningState/succeeded" ]]; then
      echo "  $vm_name agent ready"
      return 0
    fi
    sleep 10
  done
  echo "  WARNING: $vm_name agent not ready after 5 min, continuing anyway"
}

# ─── Helper: create VM only if it doesn't already exist ─────────────────────
create_vm_if_not_exists() {
  local vm_name="$1"
  local cloud_init_file="$2"
  if az vm show -g "$RESOURCE_GROUP" -n "$vm_name" --query name -o tsv 2>/dev/null; then
    echo "  ⏭️  VM '$vm_name' already exists, skipping creation"
  else
    az vm create \
      --resource-group "$RESOURCE_GROUP" \
      --name "$vm_name" \
      --image "$VM_IMAGE" \
      --size "$VM_SIZE" \
      --vnet-name "$VNET_NAME" \
      --subnet "$SUBNET_ONPREM" \
      --admin-username "$ADMIN_USERNAME" \
      --generate-ssh-keys \
      --public-ip-sku Standard \
      --nsg "" \
      --custom-data "$cloud_init_file" \
      --tags $TAGS
    echo "  ✅ VM '$vm_name' created"
  fi
}

echo "=========================================="
echo "Creating Elasticsearch VM"
echo "=========================================="

cat > /tmp/cloud-init-elasticsearch.yaml << 'CLOUDINIT'
#cloud-config
package_update: true
packages:
  - apt-transport-https
  - openjdk-17-jdk
CLOUDINIT

create_vm_if_not_exists "$VM_ELASTICSEARCH" /tmp/cloud-init-elasticsearch.yaml

echo "✅ Elasticsearch VM ready"

echo "=========================================="
echo "Creating Zabbix VM"
echo "=========================================="

cat > /tmp/cloud-init-zabbix.yaml << 'CLOUDINIT'
#cloud-config
package_update: true
packages:
  - apache2
  - mysql-server
  - php
  - php-mysql
  - php-gd
  - php-bcmath
  - php-mbstring
  - php-xml
  - php-ldap
CLOUDINIT

create_vm_if_not_exists "$VM_ZABBIX" /tmp/cloud-init-zabbix.yaml

echo "✅ Zabbix VM ready"

echo "=========================================="
echo "Creating E-Commerce Web VM (Nginx + Flask)"
echo "=========================================="

cat > /tmp/cloud-init-ecommerce.yaml << 'CLOUDINIT'
#cloud-config
package_update: true
packages:
  - nginx
  - python3-pip
  - python3-venv
CLOUDINIT

create_vm_if_not_exists "$VM_ECOMMERCE" /tmp/cloud-init-ecommerce.yaml

echo "✅ E-Commerce VM ready (Nginx + Flask)"

# ─── Wait for cloud-init to finish package installs ──────────────────────────
echo ""
echo "=========================================="
echo "Waiting for VM agents and cloud-init..."
echo "=========================================="
wait_for_vm_agent "$VM_ELASTICSEARCH"
wait_for_vm_agent "$VM_ZABBIX"
wait_for_vm_agent "$VM_ECOMMERCE"

echo "Waiting 60s for cloud-init package installs to complete..."
sleep 60

# ─── Configure Elasticsearch VM ──────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Configuring Elasticsearch + Kibana"
echo "=========================================="

cat > /tmp/setup-elasticsearch.sh << 'SETUPEOF'
#!/bin/bash
set -e

# Wait for any apt locks
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 5; done

# Install Elasticsearch repo + packages
wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --dearmor -o /usr/share/keyrings/elasticsearch-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" > /etc/apt/sources.list.d/elastic-8.x.list
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y elasticsearch kibana

# Configure Elasticsearch
cat > /etc/elasticsearch/elasticsearch.yml << 'ESYML'
cluster.name: tcc-poc
node.name: vm-elasticsearch
path.data: /var/lib/elasticsearch
path.logs: /var/log/elasticsearch
network.host: 0.0.0.0
http.port: 9200
discovery.type: single-node
xpack.security.enabled: false
xpack.security.enrollment.enabled: false
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false
ESYML

# Configure Kibana
cat > /etc/kibana/kibana.yml << 'KIBYML'
server.port: 5601
server.host: "0.0.0.0"
elasticsearch.hosts: ["http://localhost:9200"]
KIBYML

# Start services
systemctl daemon-reload
systemctl enable elasticsearch kibana
systemctl start elasticsearch
sleep 15
systemctl start kibana

# Wait for Elasticsearch to be ready
for i in $(seq 1 30); do
  if curl -s http://localhost:9200 >/dev/null 2>&1; then
    echo "Elasticsearch is running"
    break
  fi
  sleep 5
done

# Create sample index with mapping
curl -s -X PUT "http://localhost:9200/infrastructure-logs" -H 'Content-Type: application/json' -d '{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "hostname": { "type": "keyword" },
      "severity": { "type": "keyword" },
      "service": { "type": "keyword" },
      "message": { "type": "text" },
      "source": { "type": "keyword" },
      "category": { "type": "keyword" },
      "metrics": {
        "properties": {
          "cpu_percent": { "type": "float" },
          "memory_percent": { "type": "float" },
          "disk_percent": { "type": "float" },
          "network_in_bytes": { "type": "long" },
          "network_out_bytes": { "type": "long" }
        }
      },
      "ecommerce": {
        "properties": {
          "action": { "type": "keyword" },
          "status": { "type": "keyword" },
          "order_id": { "type": "keyword" },
          "customer": { "type": "keyword" },
          "product_id": { "type": "keyword" },
          "product_name": { "type": "text" },
          "price": { "type": "float" },
          "total": { "type": "float" },
          "item_count": { "type": "integer" },
          "payment_status": { "type": "keyword" }
        }
      }
    }
  }
}'

# Insert sample logs
for i in $(seq 1 20); do
  SEVERITY=$(shuf -e INFO WARNING ERROR CRITICAL -n 1)
  SERVICE=$(shuf -e nginx mysql zabbix-agent sshd cron docker gunicorn -n 1)
  HOST=$(shuf -e ecommerce-web-01 db-server-01 app-server-01 monitor-01 -n 1)
  CPU=$(shuf -i 10-95 -n 1)
  MEM=$(shuf -i 20-90 -n 1)
  curl -s -X POST "http://localhost:9200/infrastructure-logs/_doc" \
    -H 'Content-Type: application/json' -d "{
    \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
    \"hostname\": \"$HOST\",
    \"severity\": \"$SEVERITY\",
    \"service\": \"$SERVICE\",
    \"message\": \"Sample log from $SERVICE on $HOST - $SEVERITY\",
    \"source\": \"zabbix\",
    \"category\": \"infrastructure\",
    \"metrics\": {
      \"cpu_percent\": $CPU,
      \"memory_percent\": $MEM,
      \"disk_percent\": $(shuf -i 10-80 -n 1),
      \"network_in_bytes\": $(shuf -i 1000-999999 -n 1),
      \"network_out_bytes\": $(shuf -i 1000-999999 -n 1)
    }
  }" >/dev/null
done

# ─── Install & Configure Logstash ─────────────────────────────────────────
echo "Installing Logstash..."
DEBIAN_FRONTEND=noninteractive apt-get install -y logstash

# Configure Logstash pipeline: HTTP input (from E-Commerce) → Elasticsearch output
cat > /etc/logstash/conf.d/ecommerce-to-es.conf << 'LSEOF'
input {
  http {
    port => 5044
    codec => json
  }
}

filter {
  mutate {
    remove_field => ["headers", "@version", "host"]
  }
}

output {
  elasticsearch {
    hosts => ["http://localhost:9200"]
    index => "infrastructure-logs"
  }
  stdout {
    codec => rubydebug
  }
}
LSEOF

# Start Logstash
systemctl daemon-reload
systemctl enable logstash
systemctl start logstash
echo "Logstash installed and running on port 5044"

# ─── Install & Configure Zabbix Agent ─────────────────────────────────────────
echo "Installing Zabbix agent..."
cd /tmp
wget -q https://repo.zabbix.com/zabbix/6.4/ubuntu/pool/main/z/zabbix-release/zabbix-release_6.4-1+ubuntu22.04_all.deb
dpkg -i zabbix-release_6.4-1+ubuntu22.04_all.deb
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y zabbix-agent

sed -i "s/^Server=.*/Server=ZABBIX_IP_PLACEHOLDER/" /etc/zabbix/zabbix_agentd.conf
sed -i "s/^ServerActive=.*/ServerActive=ZABBIX_IP_PLACEHOLDER/" /etc/zabbix/zabbix_agentd.conf
sed -i "s/^Hostname=.*/Hostname=vm-elasticsearch/" /etc/zabbix/zabbix_agentd.conf

systemctl restart zabbix-agent
systemctl enable zabbix-agent
echo "Zabbix agent installed and pointing to ZABBIX_IP_PLACEHOLDER"

echo "Elasticsearch + Kibana + Logstash setup complete"
SETUPEOF

# Substitute Zabbix private IP into the setup script
ZABBIX_PRIV_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ZABBIX" -d --query privateIps -o tsv 2>/dev/null || echo "10.0.1.5")
sed -i "s/ZABBIX_IP_PLACEHOLDER/${ZABBIX_PRIV_IP}/g" /tmp/setup-elasticsearch.sh

az vm run-command invoke \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_ELASTICSEARCH" \
  --command-id RunShellScript \
  --scripts @/tmp/setup-elasticsearch.sh

echo "✅ Elasticsearch + Kibana configured"

# ─── Configure Zabbix VM ─────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Configuring Zabbix"
echo "=========================================="

cat > /tmp/setup-zabbix.sh << 'SETUPEOF'
#!/bin/bash
set -e

# Wait for any apt locks
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 5; done

# Install Zabbix repository + packages
cd /tmp
wget -q https://repo.zabbix.com/zabbix/6.4/ubuntu/pool/main/z/zabbix-release/zabbix-release_6.4-1+ubuntu22.04_all.deb
dpkg -i zabbix-release_6.4-1+ubuntu22.04_all.deb
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y zabbix-server-mysql zabbix-frontend-php zabbix-apache-conf zabbix-sql-scripts zabbix-agent

# Configure MySQL
systemctl start mysql
systemctl enable mysql
mysql -e "CREATE DATABASE IF NOT EXISTS zabbix CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;"
mysql -e "CREATE USER IF NOT EXISTS 'zabbix'@'localhost' IDENTIFIED WITH mysql_native_password BY 'zabbix_poc_pass';"
mysql -e "ALTER USER 'zabbix'@'localhost' IDENTIFIED WITH mysql_native_password BY 'zabbix_poc_pass';"
mysql -e "GRANT ALL PRIVILEGES ON zabbix.* TO 'zabbix'@'localhost';"
mysql -e "FLUSH PRIVILEGES;"
mysql -e "SET GLOBAL log_bin_trust_function_creators = 1;"

# Import Zabbix schema if not done yet
TABLE_COUNT=$(mysql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='zabbix';")
if [ "$TABLE_COUNT" -lt 10 ]; then
  zcat /usr/share/zabbix-sql-scripts/mysql/server.sql.gz | mysql --default-character-set=utf8mb4 zabbix
fi

# Configure Zabbix server
sed -i 's/^# DBPassword=$/DBPassword=zabbix_poc_pass/' /etc/zabbix/zabbix_server.conf
grep -q '^DBPassword=zabbix_poc_pass' /etc/zabbix/zabbix_server.conf || echo 'DBPassword=zabbix_poc_pass' >> /etc/zabbix/zabbix_server.conf

# Start services
systemctl restart zabbix-server zabbix-agent apache2
systemctl enable zabbix-server zabbix-agent apache2

echo "Zabbix setup complete"
SETUPEOF

az vm run-command invoke \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_ZABBIX" \
  --command-id RunShellScript \
  --scripts @/tmp/setup-zabbix.sh

echo "✅ Zabbix configured"

# ─── Configure E-Commerce VM ─────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Configuring E-Commerce App"
echo "=========================================="

ES_PRIVATE_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ELASTICSEARCH" -d --query privateIps -o tsv 2>/dev/null || echo "10.0.1.4")
ZABBIX_PRIVATE_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ZABBIX" -d --query privateIps -o tsv 2>/dev/null || echo "10.0.1.5")

# Create setup script with IPs substituted
sed -e "s/ES_IP_PLACEHOLDER/${ES_PRIVATE_IP}/g" -e "s/ZABBIX_IP_PLACEHOLDER/${ZABBIX_PRIVATE_IP}/g" > /tmp/setup-ecommerce.sh << 'SETUPEOF'
#!/bin/bash
set -e

# Wait for any apt locks
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 5; done

# Create app directory and venv
mkdir -p /opt/ecommerce
python3 -m venv /opt/ecommerce/venv
/opt/ecommerce/venv/bin/pip install -q flask requests gunicorn

# Create systemd service
cat > /etc/systemd/system/ecommerce.service << 'SVCEOF'
[Unit]
Description=TCC E-Commerce Flask App (Gunicorn)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/ecommerce
Environment="LOGSTASH_URL=http://ES_IP_PLACEHOLDER:5044"
ExecStart=/opt/ecommerce/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

# Configure Nginx
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-available/ecommerce << 'NGXEOF'
server {
    listen 80;
    server_name _;
    access_log /var/log/nginx/ecommerce_access.log;
    error_log  /var/log/nginx/ecommerce_error.log;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
NGXEOF
ln -sf /etc/nginx/sites-available/ecommerce /etc/nginx/sites-enabled/ecommerce

# Install Zabbix agent for monitoring
cd /tmp
wget -q https://repo.zabbix.com/zabbix/6.4/ubuntu/pool/main/z/zabbix-release/zabbix-release_6.4-1+ubuntu22.04_all.deb
dpkg -i zabbix-release_6.4-1+ubuntu22.04_all.deb
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y zabbix-agent

# Configure Zabbix agent to report to Zabbix server
sed -i "s/^Server=.*/Server=ZABBIX_IP_PLACEHOLDER/" /etc/zabbix/zabbix_agentd.conf
sed -i "s/^ServerActive=.*/ServerActive=ZABBIX_IP_PLACEHOLDER/" /etc/zabbix/zabbix_agentd.conf
sed -i "s/^Hostname=.*/Hostname=vm-ecommerce/" /etc/zabbix/zabbix_agentd.conf

# Custom UserParameters for E-Commerce monitoring
cat >> /etc/zabbix/zabbix_agentd.conf << UEOF

# E-Commerce app monitoring
UserParameter=ecommerce.health,curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/health 2>/dev/null || echo 0
UserParameter=ecommerce.gunicorn.workers,pgrep -c gunicorn 2>/dev/null || echo 0
UEOF

systemctl restart zabbix-agent
systemctl enable zabbix-agent

echo "E-Commerce infra ready"
SETUPEOF

az vm run-command invoke \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_ECOMMERCE" \
  --command-id RunShellScript \
  --scripts @/tmp/setup-ecommerce.sh

# Deploy app.py via SCP
ECOMMERCE_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ECOMMERCE" -d --query publicIps -o tsv)
echo "Deploying app.py to E-Commerce VM ($ECOMMERCE_IP)..."
scp -o StrictHostKeyChecking=no "$SCRIPT_DIR/../ecommerce-app/app.py" "${ADMIN_USERNAME}@${ECOMMERCE_IP}:/tmp/app.py"

az vm run-command invoke \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_ECOMMERCE" \
  --command-id RunShellScript \
  --scripts "cp /tmp/app.py /opt/ecommerce/app.py && chown -R www-data:www-data /opt/ecommerce && systemctl daemon-reload && systemctl enable ecommerce nginx && systemctl restart ecommerce nginx && sleep 3 && curl -s http://localhost/health"

echo "✅ E-Commerce configured"

# ─── Register hosts in Zabbix ─────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Registering VMs in Zabbix monitoring"
echo "=========================================="

ZABBIX_PRIVATE_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ZABBIX" -d --query privateIps -o tsv 2>/dev/null || echo "10.0.1.5")
ECOMMERCE_PRIVATE_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ECOMMERCE" -d --query privateIps -o tsv 2>/dev/null || echo "10.0.1.6")
ES_PRIVATE_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ELASTICSEARCH" -d --query privateIps -o tsv 2>/dev/null || echo "10.0.1.4")

cat > /tmp/register-zabbix-hosts.sh << REGEOF
#!/bin/bash
set -e
ZABBIX_URL="http://localhost/zabbix/api_jsonrpc.php"

# Wait for Zabbix API to be ready
for i in \$(seq 1 12); do
  if python3 -c "
import urllib.request, json
data = json.dumps({\"jsonrpc\": \"2.0\", \"method\": \"apiinfo.version\", \"params\": [], \"id\": 1}).encode()
req = urllib.request.Request('\$ZABBIX_URL', data=data, headers={'Content-Type': 'application/json-rpc'})
resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
print(resp.get('result', ''))
" 2>/dev/null; then
    break
  fi
  sleep 5
done

# Register hosts via Zabbix API
python3 << 'PYEOF'
import urllib.request, json, sys

ZABBIX_URL = "http://localhost/zabbix/api_jsonrpc.php"

def zabbix_api(method, params, auth=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if auth:
        payload["auth"] = auth
    data = json.dumps(payload).encode()
    req = urllib.request.Request(ZABBIX_URL, data=data, headers={"Content-Type": "application/json-rpc"})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())

# Login
auth = zabbix_api("user.login", {"username": "Admin", "password": "zabbix"}).get("result")
if not auth:
    print("Zabbix auth failed"); sys.exit(1)

# Get template + group IDs
tpl = zabbix_api("template.get", {"filter": {"host": ["Linux by Zabbix agent"]}}, auth).get("result", [])
tpl_id = tpl[0]["templateid"] if tpl else None
grp = zabbix_api("hostgroup.get", {"filter": {"name": ["Linux servers"]}}, auth).get("result", [])
grp_id = grp[0]["groupid"] if grp else None

if not grp_id:
    print("No Linux servers group found"); sys.exit(1)

hosts = [
    {"host": "vm-ecommerce", "name": "E-Commerce App (TCC Shop)",
     "ip": "$ECOMMERCE_PRIVATE_IP", "templates": [{"templateid": tpl_id}] if tpl_id else []},
    {"host": "vm-elasticsearch", "name": "Elasticsearch + Kibana + Logstash",
     "ip": "$ES_PRIVATE_IP", "templates": [{"templateid": tpl_id}] if tpl_id else []},
]
for h in hosts:
    existing = zabbix_api("host.get", {"filter": {"host": [h["host"]]}}, auth).get("result", [])
    if existing:
        print(f"Host {h['host']} already registered")
        continue
    result = zabbix_api("host.create", {
        "host": h["host"], "name": h["name"],
        "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": h["ip"], "dns": "", "port": "10050"}],
        "groups": [{"groupid": grp_id}],
        "templates": h["templates"],
        "description": f"TCC PoC - {h['name']}"
    }, auth)
    if "error" in result:
        print(f"Error registering {h['host']}: {result['error']}")
    else:
        print(f"Registered {h['host']} (hostid: {result['result']['hostids'][0]})")
PYEOF
REGEOF

az vm run-command invoke \
  --resource-group "$RESOURCE_GROUP" \
  --name "$VM_ZABBIX" \
  --command-id RunShellScript \
  --scripts @/tmp/register-zabbix-hosts.sh

echo "✅ VMs registered in Zabbix (E-Commerce + Elasticsearch)"

# ─── Summary ──────────────────────────────────────────────────────────────────
ES_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ELASTICSEARCH" -d --query publicIps -o tsv)
ZABBIX_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ZABBIX" -d --query publicIps -o tsv)
ECOMMERCE_IP=$(az vm show --resource-group "$RESOURCE_GROUP" --name "$VM_ECOMMERCE" -d --query publicIps -o tsv)

echo ""
echo "=========================================="
echo "VM Details:"
echo "  Elasticsearch API: http://$ES_IP:9200"
echo "  Kibana (ES UI):    http://$ES_IP:5601"
echo "  Zabbix Dashboard:  http://$ZABBIX_IP/zabbix  (Admin / zabbix)"
echo "  E-Commerce Shop:   http://$ECOMMERCE_IP (Nginx → Flask)"
echo "=========================================="
