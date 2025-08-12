#!/bin/bash

# Multi-architecture Docker build and push script for Google Cloud Run
# Usage: Set PROJECT_ID before running, e.g. export PROJECT_ID=my-gcp-project
#        ./build_multiarch_and_run.sh

set -e

if [ -z "$PROJECT_ID" ]; then
  echo "Error: PROJECT_ID environment variable not set."
  echo "Please run: export PROJECT_ID=your-gcp-project-id"
  exit 1
fi

IMAGE_NAME=gcr.io/$PROJECT_ID/yt-scorer:latest

# 1. Multi-architecture Build & Push to Google Container Registry (GCR)
echo "[1/3] Creating and using buildx builder (if not already present)..."
docker buildx create --use || docker buildx use default

echo "[2/3] Building and pushing multi-architecture image to $IMAGE_NAME ..."
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t $IMAGE_NAME \
  --push \
  .

echo "[3/3] (Optional) Run the image locally (amd64 only, for testing):"
echo "    docker run -it --rm -p 8080:8080 $IMAGE_NAME"
echo ""
echo "---"
echo "Alternative: Google Cloud Build (no local Docker required)"
echo "gcloud auth login"
echo "gcloud config set project $PROJECT_ID"
echo "gcloud builds submit --tag $IMAGE_NAME"
echo "---"

echo "Done." 