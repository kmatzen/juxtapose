#!/bin/bash

# Auto-install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install dependencies
echo "Installing dependencies..."
uv sync

# Set dev mode environment variable
export DEV_MODE=true

# Run the application
echo "Starting survey app in DEV MODE..."
echo "Visit http://127.0.0.1:5000"
uv run python run.py
