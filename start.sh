#!/bin/bash

# Survey App Startup Script

echo "==================================="
echo "   Survey Web Application"
echo "==================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install dependencies and sync environment
echo "Installing dependencies with uv (this is fast!)..."
uv sync

# Set default admin password if not set
if [ -z "$ADMIN_PASSWORD" ]; then
    export ADMIN_PASSWORD="admin123"
    echo ""
    echo "⚠️  Using default admin password: admin123"
    echo "   Change this by setting ADMIN_PASSWORD environment variable"
fi

echo ""
echo "==================================="
echo "Starting Flask application..."
echo "==================================="
echo ""
echo "Access the survey at: http://localhost:5000"
echo "Admin panel at: http://localhost:5000/admin/login"
echo ""
echo "To expose this publicly with ngrok:"
echo "  1. Install ngrok from https://ngrok.com/download"
echo "  2. Run: ngrok http 5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the application with uv
uv run python run.py

