# FocusTube - Backend Scoring API

This repository contains the backend service for the FocusTube project. It is a Python Flask application, containerized with Docker, that uses sentence-transformer models to provide a video relevance score.

## Features
- **AI-Powered Scoring:** Uses an ensemble of sentence-transformer models to analyze text.
- **REST API:** Exposes a simple `/predict` endpoint to score videos.
- **Containerized:** Designed to be built and deployed anywhere using Docker, currently running on Google Cloud Run.

## Local Setup
1.  Ensure you have Python and Docker installed.
2.  Install dependencies: `pip install -r requirements.txt`
3.  Download the required AI models by running the setup script: `python download_models.py`
4.  Set the `YOUTUBE_API_KEY` environment variable.
5.  Build the Docker image: `docker build -t focustube-backend .`
6.  Run the container: `docker run -p 8080:8080 -e YOUTUBE_API_KEY="YOUR_API_KEY" focustube-backend`

The API will now be available at `http://localhost:8080`.

## Deployment to Google Cloud

These commands outline the process for deploying the container to Google Cloud Run.

### 1. Authenticate and Configure gcloud
First, log in to your Google Cloud account and set your project ID.
```bash
# Log in to your Google account
gcloud auth login

# Set your active project (replace $PROJECT_ID with your actual project ID)
gcloud config set project $PROJECT_ID

2. Build and Push the Image to Google Container Registry (GCR)
This command uses Google Cloud Build to build your Docker image and push it to GCR.

gcloud builds submit --tag gcr.io/$PROJECT_ID/yt-scorer:latest

3. Deploy the Image to Cloud Run
This command deploys the image from GCR as a new service on Cloud Run.

# Replace YOUR_KEY_HERE with your actual YouTube API key
gcloud run deploy yt-scorer \
  --image gcr.io/$PROJECT_ID/yt-scorer:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars YOUTUBE_API_KEY=YOUR_KEY_HERE

After deployment, Google Cloud will provide you with a public URL for your service.

4. Test the Deployed Endpoint
You can test the live endpoint using curl.

# Replace the URL with the one provided by Cloud Run
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"video_url":"[https://youtu.be/dQw4w9WgXcQ](https://youtu.be/dQw4w9WgXcQ)", "goal": "learn guitar"}' \
  https://yt-scorer-<hash>.us-central1.run.app/predict
