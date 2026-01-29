#!/bin/bash

# Define the venv python path pattern
VENV_PYTHON=".venv/bin/python"

echo "🧹 Finding processes to kill..."

# Find pids
PIDS=$(pgrep -f "$VENV_PYTHON")

if [ -z "$PIDS" ]; then
    echo "✅ No active agent/benchmark processes found."
else
    echo "⚠️ Found processes: $PIDS"
    echo "☠️  Killing processes..."
    
    # Kill them
    pkill -9 -f "$VENV_PYTHON"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully killed processes."
    else
        echo "❌ Failed to kill some processes (or they exited already)."
    fi
fi
