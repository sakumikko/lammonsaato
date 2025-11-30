#!/bin/bash
# Run a command with .env file loaded
# Usage: ./scripts/run-with-env.sh <command>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    # Read .env line by line to handle special characters
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue

        # Export the variable
        export "$line"
    done < "$PROJECT_ROOT/.env"
fi

# Run the command
exec "$@"
