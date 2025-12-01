#!/bin/bash
set -e

echo "Building Lämmönsäätö UI add-on..."

# Build the web app
echo "Building web app..."
npm run build

# Prepare addon directory
echo "Preparing add-on package..."
rm -rf addon/dist
cp -r dist addon/

echo "Add-on build complete!"
echo ""
echo "To install locally:"
echo "1. Copy the 'addon' directory to your Home Assistant /addons/ folder"
echo "2. In HA, go to Settings -> Add-ons -> Add-on Store"
echo "3. Click the three dots menu -> Check for updates"
echo "4. The add-on should appear in 'Local add-ons'"
