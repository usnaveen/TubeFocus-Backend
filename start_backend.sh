#!/bin/bash

# TubeFocus Backend Startup Script
# This script helps you start the backend server with proper checks

echo "🚀 TubeFocus AI Agents - Backend Startup"
echo "========================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "   Install it from: https://www.python.org/downloads/"
    echo "   Or use: brew install python3"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if .env file exists
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  Warning: .env file not found"
    echo ""
    echo "Creating .env file from template..."
    cat > .env << 'EOF'
# TubeFocus Backend Configuration
GOOGLE_API_KEY=your_gemini_api_key_here
YOUTUBE_API_KEY=your_youtube_api_key_here
API_KEY=test_key
PORT=8080
ENVIRONMENT=development
DEBUG=True
EOF
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your Gemini API key!"
    echo "   Get one here: https://makersuite.google.com/app/apikey"
    echo ""
    echo "Press Enter after you've edited .env..."
    read
fi

# Check if requirements are installed
echo ""
echo "📦 Checking dependencies..."

if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  Dependencies not installed. Installing now..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

# Check if port 8080 is available
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo ""
    echo "⚠️  Warning: Port 8080 is already in use"
    echo "   Kill the process? (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        kill -9 $(lsof -ti:8080) 2>/dev/null
        echo "✅ Killed process on port 8080"
    else
        echo "❌ Cannot start server - port 8080 is busy"
        exit 1
    fi
fi

# Start the server
echo ""
echo "🎯 Starting TubeFocus Backend Server..."
echo "   API will be available at: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo ""

python3 api.py
