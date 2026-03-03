#!/bin/bash
# Auto-restarting localtunnel — keeps the tunnel alive forever.
# Run this in a dedicated terminal tab and leave it open.

LT="$HOME/.nvm/versions/node/v24.14.0/bin/node $HOME/.nvm/versions/node/v24.14.0/bin/lt"

echo "Starting tunnel watcher..."

while true; do
    echo "[$(date '+%H:%M:%S')] Starting localtunnel..."
    $LT --port 8000 --subdomain fraudagent
    echo "[$(date '+%H:%M:%S')] Tunnel exited. Restarting in 2 seconds..."
    sleep 2
done
