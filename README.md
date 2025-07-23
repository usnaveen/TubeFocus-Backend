# YouTube Productivity Score Backend

## Overview
This backend provides two main services:
- **Video Productivity Scoring**: Scores YouTube videos for relevance to a user-defined goal using sentence transformers.
- **Witty Session Summary**: Accepts a session history and goal, and generates a witty, goal-aware summary using Vertex AI Gemini 1.5 Flash.

## Features
- `/predict` endpoint: Score a single YouTube video for relevance to a goal (supports `title_only` and `title_and_description` modes).
- `/upload` endpoint: Accept a session's video titles and user goal, and return a witty summary using Gemini 1.5 Flash.
- Dockerized for easy deployment (Cloud Run, GCE, or local).

## Endpoints

### 1. `/predict` (POST)
- **Purpose:** Score a YouTube video for relevance to a user goal.
- **Request:**
  ```json
  {
    "video_url": "https://www.youtube.com/watch?v=...",
    "goal": "learn about music videos",
    "mode": "title_and_description" // or "title_only"
  }
  ```
- **Response:**
  ```json
  { "score": 62 }
  ```

### 2. `/upload` (POST)
- **Purpose:** Generate a witty, goal-aware summary of a session using Gemini 1.5 Flash.
- **Request:**
  ```json
  {
    "goal": "learn about music videos",
    "session": [
      {"title": "Never Gonna Give You Up"},
      {"title": "How Music Videos Are Made"}
    ]
  }
  ```
- **Response:**
  ```json
  { "summary": "[Witty summary text from Gemini]" }
  ```

## Setup & Usage

### 1. Build and Run with Docker
```sh
cd "YouTube Productivity Score Docker Container"
docker build -t yt-scorer-backend:latest .
docker run -d -p 8080:8080 --name yt-scorer-backend yt-scorer-backend:latest
```

### 2. Vertex AI Gemini 1.5 Flash Setup
- Enable Vertex AI API in your Google Cloud project.
- Create a service account with Vertex AI permissions.
- Download the JSON key and set these environment variables:
  ```sh
  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
  export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
  ```
- The `/upload` endpoint will now use Gemini 1.5 Flash for witty summaries.

### 3. Example Usage
- Health check:
  ```sh
  curl http://localhost:8080/
  ```
- Score a video:
  ```sh
  curl -X POST http://localhost:8080/predict -H 'Content-Type: application/json' \
    -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "goal": "learn about music videos", "mode": "title_and_description"}'
  ```
- Upload a session for summary:
  ```sh
  curl -X POST http://localhost:8080/upload -H 'Content-Type: application/json' \
    -d '{"goal": "learn about music videos", "session": [{"title": "Never Gonna Give You Up"}, {"title": "How Music Videos Are Made"}]}'
  ```

## Development
- Main code: `app.py`, `score_model.py`, `youtube_scraper.py`
- Models: Downloaded to `models/` directory
- Requirements: `requirements.txt`

## Notes
- The `/upload` endpoint requires Google Cloud credentials and access to Vertex AI Gemini 1.5 Flash.
- The `/predict` endpoint works locally and in the cloud, and does not require Google Cloud unless you use Gemini.

## License
MIT

