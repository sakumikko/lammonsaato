#!/bin/bash
set -e

HA_HOST="${HA_HOST:-192.168.50.11}"

# HA_TOKEN must be set in environment - never commit tokens!
if [ -z "$HA_TOKEN" ]; then
    echo "Error: HA_TOKEN environment variable not set"
    echo "Set it with: export HA_TOKEN=your_token_here"
    exit 1
fi

echo "=== Building everything (backend + web UI) ==="
make build-all

echo "=== Copying packages and pyscript to HA ==="
scp dist/packages/pool_heating.yaml root@${HA_HOST}:/config/packages/
scp dist/packages/thermia_protection.yaml root@${HA_HOST}:/config/packages/
scp dist/packages/peak_power.yaml root@${HA_HOST}:/config/packages/
scp dist/packages/thermia_recording.yaml root@${HA_HOST}:/config/packages/
scp dist/pyscript/* root@${HA_HOST}:/config/pyscript/

echo "=== Reloading pyscript in HA ==="
curl -s -X POST -H "Authorization: Bearer $HA_TOKEN" \
  "http://${HA_HOST}:8123/api/services/pyscript/reload"
sleep 2

echo "=== Cleaning old addon files on server ==="
ssh root@${HA_HOST} "rm -rf /addons/lammonsaato-ui/dist"

echo "=== Copying addon to HA ==="
scp -r web-ui/addon/* root@${HA_HOST}:/addons/lammonsaato-ui/

echo ""
echo "=== Deployment complete ==="
