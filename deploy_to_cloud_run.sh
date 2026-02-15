#!/bin/bash

# Deploy to Google Cloud Run script
# Usage: ./deploy_to_cloud_run.sh

set -e

# Load .env file if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Check for required environment variables
if [ -z "$PROJECT_ID" ]; then
    # Try to get default project from gcloud config
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
fi

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID environment variable not set and no default project configured."
  echo "Please set it: export PROJECT_ID=your-gcp-project-id"
  echo "Or run: gcloud config set project your-gcp-project-id"
  exit 1
fi

if [ -z "$YOUTUBE_API_KEY" ] || [ -z "$GOOGLE_API_KEY" ]; then
    echo "Warning: API keys not found in environment or .env file."
    echo "Deployment may succeed, but the service will fail to run correctly."
fi

SERVICE_NAME="yt-scorer-api"
REGION="us-central1"

echo "🚀 Deploying to Google Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region:  $REGION"
echo ""

# Deploy to Cloud Run from source
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 5 \
  --timeout 300 \
  --set-env-vars "YOUTUBE_API_KEY=$YOUTUBE_API_KEY" \
  --set-env-vars "GOOGLE_API_KEY=$GOOGLE_API_KEY" \
  --set-env-vars "API_KEY=${API_KEY:-changeme}" \
  --set-env-vars "FLASK_ENV=production" \
  --set-env-vars "SKIP_CONFIG_VALIDATION=true"

echo ""
echo "✅ Deployment completed!"
 