#!/bin/bash

# TubeFocus Backend Server Startup Script
# Run this script to start the backend server

cd "/Users/naveenus/Library/Mobile Documents/com~apple~CloudDocs/Projects/TubeFocus/YouTube Productivity Score Development Container"

echo "🚀 Starting TubeFocus Backend Server..."
echo "========================================"
echo ""

# Activate virtual environment
source venv/bin/activate

# Start the server
echo "Server will be available at: http://localhost:8080"
echo "Press Ctrl+C to stop the server"
echo ""
python3 api.py
