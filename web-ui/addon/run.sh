#!/bin/sh
set -e

echo "Starting Lämmönsäätö UI..."

# Create runtime config with supervisor token
# (index.html already has <script src="./config.js"> reference)
cat > /var/www/html/config.js << EOF
window.__SUPERVISOR_TOKEN__ = "${SUPERVISOR_TOKEN}";
EOF

echo "Supervisor token configured"
echo "Starting nginx on port 8099..."

# Start nginx in foreground
exec nginx -g "daemon off;"
