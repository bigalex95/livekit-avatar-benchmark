#!/bin/bash
set -e

# Change to project root directory
cd "$(dirname "$0")/.."

# Define paths to binaries
VENV_BIN=".venv/bin"
RUFF="$VENV_BIN/ruff"
PYTEST="$VENV_BIN/pytest"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found in .venv"
    exit 1
fi

echo "🚀 Starting Quality Checks & Tests..."

echo "------------------------------------------------"
echo "📦 Running Ruff Format..."
"$RUFF" format .

echo "------------------------------------------------"
echo "🔍 Running Ruff Check (Linting)..."
"$RUFF" check . --fix

echo "------------------------------------------------"
echo "🧪 Running Pytest..."
"$PYTEST" -v tests/test_agent_integration.py

echo "------------------------------------------------"
echo "✅ All checks passed!"
