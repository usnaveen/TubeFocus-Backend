#!/bin/bash

# Build and Test Script for TubeFocus API
# This script builds the Docker container and tests it locally

set -e  # Exit on any error

echo "🚀 Building TubeFocus API Docker container..."

# Build the Docker image
docker build -t tubefocus-api:latest .

echo "✅ Docker image built successfully!"

# Check if container is already running and stop it
if [ "$(docker ps -q -f name=tubefocus-api)" ]; then
    echo "🛑 Stopping existing container..."
    docker stop tubefocus-api
    docker rm tubefocus-api
fi

echo "🔧 Starting container for local testing..."

# Run the container locally
docker run -d \
    --name tubefocus-api \
    -p 8080:8080 \
    -e API_KEY=changeme \
    -e YOUTUBE_API_KEY=${YOUTUBE_API_KEY:-} \
    tubefocus-api:latest

echo "⏳ Waiting for container to start..."
sleep 5

# Test the health endpoint
echo "🏥 Testing health endpoint..."
if curl -f http://localhost:8080/health; then
    echo "✅ Health check passed!"
else
    echo "❌ Health check failed!"
    echo "📋 Container logs:"
    docker logs tubefocus-api
    exit 1
fi

# Test the predict endpoint
echo "🧪 Testing predict endpoint..."
curl -X POST http://localhost:8080/predict \
    -H "Content-Type: application/json" \
    -H "X-API-KEY: changeme" \
    -d '{
        "video_id": "dQw4w9WgXcQ",
        "goal": "watch educational content",
        "parameters": ["title", "description"]
    }' | jq .

echo "✅ Local testing completed!"
echo ""
echo "📋 Container is running at http://localhost:8080"
echo "🛑 To stop the container: docker stop tubefocus-api"
echo "🗑️  To remove the container: docker rm tubefocus-api"
echo ""
echo "🌐 Ready for Cloud Run deployment!" 