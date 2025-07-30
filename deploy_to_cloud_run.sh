#!/bin/bash

# Deploy to Google Cloud Run script
# Usage: ./deploy_to_cloud_run.sh

set -e

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID environment variable not set."
  echo "Please run: export PROJECT_ID=your-gcp-project-id"
  exit 1
fi

SERVICE_NAME="yt-scorer-api"
IMAGE_NAME="gcr.io/$PROJECT_ID/yt-scorer:latest"
REGION="us-central1"  # You can change this to your preferred region

echo "Deploying to Google Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Image: $IMAGE_NAME"
echo "Region: $REGION"
echo ""

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 4Gi \
  --cpu 2 \
  --max-instances 10 \
  --timeout 300 \
  --set-env-vars "API_KEY=changeme" \
  --set-env-vars "FLASK_ENV=production"

echo ""
echo "✅ Deployment completed!"
echo "Service URL: https://$SERVICE_NAME-$REGION-$PROJECT_ID.a.run.app"
echo ""
echo "To get the service URL:"
echo "gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'" 