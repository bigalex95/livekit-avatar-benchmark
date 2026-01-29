#!/bin/bash

# Change to project root directory
cd "$(dirname "$0")/.."

# Function to run when script exits (e.g. via Ctrl+C)
cleanup() {
    echo ""
    echo "🛑 Shutting down containers..."
    docker compose down
}

# Trap EXIT so cleanup runs whenever the script ends
trap cleanup EXIT

# 1. Stop any old containers
echo "🛑 Stopping old containers..."
docker compose down

# 2. Start Docker in Background (Detached)
echo "🚀 Starting LiveKit + Agent..."
docker compose up -d --build

# 3. Wait a moment for server to be ready
echo "⏳ Waiting for server..."
sleep 3

# 4. Generate a token for YOU (The Human)
echo "🔑 Generating manual test token..."
python scripts/generate_token.py

# 5. Show logs so you can see what's happening
echo "📜 Tailing logs (Press Ctrl+C to stop EVERYTHING)..."
docker compose logs -f