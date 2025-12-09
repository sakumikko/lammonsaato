#!/bin/bash
set -e

HA_HOST="${HA_HOST:-192.168.50.11}"

# HA_TOKEN must be set in environment - never commit tokens!
if [ -z "$HA_TOKEN" ]; then
    echo "Error: HA_TOKEN environment variable not set"
    echo "Set it with: export HA_TOKEN=your_token_here"
    exit 1
fi

echo "=== Building distribution ==="
make dist

echo "=== Copying packages and pyscript to HA ==="
scp dist/packages/pool_heating.yaml root@${HA_HOST}:/config/packages/
scp dist/pyscript/* root@${HA_HOST}:/config/pyscript/

echo "=== Reloading pyscript in HA ==="
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" \
  "http://${HA_HOST}:8123/api/services/pyscript/reload"
sleep 2

echo "=== Testing apply_cost_constraint service ==="
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  "http://${HA_HOST}:8123/api/services/pyscript/apply_cost_constraint"
sleep 1

echo ""
echo "=== Verifying constraint status ==="
echo "cost_limit_applied:"
curl -s -H "Authorization: Bearer $HA_TOKEN" \
  "http://${HA_HOST}:8123/api/states/input_boolean.pool_heating_cost_limit_applied" | python3 -c "import sys,json; print(json.load(sys.stdin).get('state','error'))"

echo "block_1_cost_exceeded:"
curl -s -H "Authorization: Bearer $HA_TOKEN" \
  "http://${HA_HOST}:8123/api/states/input_boolean.pool_heat_block_1_cost_exceeded" | python3 -c "import sys,json; print(json.load(sys.stdin).get('state','error'))"

echo ""
echo "=== Building web-ui ==="
cd web-ui && npm run build

echo "=== Cleaning old addon files on server ==="
ssh root@${HA_HOST} "rm -rf /addons/lammonsaato-ui/dist"

echo "=== Copying addon to HA ==="
rm -rf addon/dist
cp -r dist addon/dist
scp -r addon/* root@${HA_HOST}:/addons/lammonsaato-ui/

echo ""
echo "=== Deployment complete ==="
