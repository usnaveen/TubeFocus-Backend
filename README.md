# YouTube Productivity Score Backend - Development Container

## Overview
This backend provides advanced ML-powered services for the TubeFocus Chrome extension:
- **Advanced Video Productivity Scoring**: Uses ensemble of sentence transformers and zero-shot classification models for highly accurate relevance scoring.
- **Multi-Modal Analysis**: Analyzes video titles, descriptions, tags, and categories for comprehensive scoring.
- **Model Training**: Includes MLP regressor for personalized scoring based on user feedback.

## Features

### Advanced ML Scoring System
- **Ensemble Models**: Uses multiple sentence transformers for robust scoring
- **Zero-Shot Classification**: BART-large-MNLI for topic classification
- **Cross-Encoder**: MS-Marco model for fine-grained relevance scoring
- **Multi-Modal Analysis**: Title, description, tags, and category scoring
- **Personalized Training**: MLP regressor learns from user feedback

### Simplified Scoring System
- **5 Sentence Transformers**: Ensemble of 5 models for reliable scoring
- **Text Cleaning**: Intelligent filtering of description noise
- **Three Modes**: title_only, title_and_description, title_and_clean_desc
- **Fast Processing**: Optimized for quick response times
- **Docker-Compatible**: Same approach as production container

### API Endpoints
- `/score/detailed` endpoint: Advanced scoring with multiple ML models and detailed analysis.
- `/score/simple` endpoint: Simplified scoring with 3 modes (title_only, title_and_description, title_and_clean_desc)
- `/feedback` endpoint: Collect and store user feedback for model training.
- `/health` endpoint: Health check for the API.

## ML Models Used

### Sentence Transformers (Ensemble)
- `all-MiniLM-L6-v2`: Fast, general-purpose embeddings
- `multi-qa-MiniLM-L6-cos-v1`: Optimized for question-answer similarity
- `paraphrase-MiniLM-L3-v2`: Specialized for paraphrase detection
- `all-mpnet-base-v2`: High-quality semantic embeddings
- `all-distilroberta-v1`: Robust RoBERTa-based embeddings

### Zero-Shot Classification
- `facebook/bart-large-mnli`: For zero-shot topic classification

### Cross-Encoder
- `cross-encoder/ms-marco-MiniLM-L6-v2`: For re-ranking and fine-grained scoring

## Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

**IMPORTANT:** This project now uses Gemini API instead of local ML models.

Create a `.env` file from the template:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```bash
# Required API Keys
YOUTUBE_API_KEY=your_youtube_api_key_here
GOOGLE_API_KEY=your_google_gemini_api_key_here
API_KEY=your_secure_api_key_here
```

**Where to get API keys:**
- **YouTube Data API v3**: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- **Google Gemini API**: [Google AI Studio](https://makersuite.google.com/app/apikey)
- **API_KEY**: Create your own secure key for protecting your endpoints

### 3. Run the Development Server
```bash
python api.py
```

The server will start on `http://localhost:8080` by default.

## API Endpoints

### 1. `/score/detailed` (POST) - Detailed Scoring
Advanced scoring with multiple ML models and detailed analysis.
```json
{
  "video_id": "dQw4w9WgXcQ",
  "goal": "learn about music videos",
  "parameters": ["title", "description", "tags", "category"]
}
```
**Response:**
```json
{
  "title_score": 0.85,
  "description_score": 0.72,
  "tags_score": 0.65,
  "category_score": 0.90,
  "category_name": "Education",
  "score": 0.78
}
```

### 2. `/score/simple` (POST) - Simplified Scoring
Simplified scoring using 5 sentence transformers with 3 different modes.
```json
{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "goal": "learn about music videos",
  "mode": "title_and_clean_desc"
}
```
**Response:**
```json
{
  "score": 75,
  "mode": "title_and_clean_desc"
}
```
**Available Modes:**
- `title_only`: Uses only video title (fastest)
- `title_and_description`: Uses title + full description (most comprehensive)
- `title_and_clean_desc`: Uses title + cleaned description (filters noise)

### 3. `/feedback` (POST) - User Feedback
Collect user feedback for model training.
```json
{
  "desc_score": 0.72,
  "title_score": 0.85,
  "tags_score": 0.65,
  "category_score": 0.90,
  "user_score": 4.5
}
```
**Response:**
```json
{
  "status": "Feedback saved",
  "retrained": true
}
```

### 4. `/health` (GET) - Health Check
Checks if the API is running.
**Response:** `YouTube Relevance Scorer API is running!`

## Development Tools

### Model Management
- `download_all_models.py`: Download all required ML models
- `download_models.py`: Download sentence transformer models
- `fix_cross_encoder_download.py`: Fix cross-encoder model download
- `bigmodeltest.py`: Test and compare different models

### Testing Scripts
- `test_models.py`: Test model performance
- `test_title_scoring.py`: Test title scoring functionality
- `test_description_scoring.py`: Test description scoring
- `test_tag_scoring.py`: Test tag scoring
- `test_category_scoring.py`: Test category scoring
- `test_youtube_metadata.py`: Test YouTube API integration

### Training and Feedback
- `model_trainer.py`: MLP regressor training and model management
- `data_manager.py`: Feedback data storage and retrieval
- `main.py`: Interactive testing and feedback collection

## File Structure
```
YouTube Productivity Score Development Container/
├── api.py                          # Main Flask application with all endpoints
├── simple_scoring.py               # Simplified scoring implementation
├── scoring_modules.py              # Advanced ML scoring modules
├── youtube_scraper.py              # YouTube metadata fetching
├── youtube_api.py                  # YouTube API integration
├── model_trainer.py                # ML model training
├── data_manager.py                 # Feedback data management
├── config.py                       # Configuration management
├── requirements.txt                # Python dependencies
├── download_all_models.py          # Model download script
├── models/                         # Downloaded ML models
├── test_*.py                       # Testing scripts
└── README.md                       # This file
```

## Usage Examples

### Detailed Video Scoring
```bash
curl -X POST http://localhost:8080/score/detailed \
  -H 'Content-Type: application/json' \
  -H 'X-API-KEY: your_api_key' \
  -d '{
    "video_id": "dQw4w9WgXcQ",
    "goal": "learn about music videos",
    "parameters": ["title", "description"]
  }'
```

### Simplified Video Scoring
```bash
curl -X POST http://localhost:8080/score/simple \
  -H 'Content-Type: application/json' \
  -H 'X-API-KEY: your_api_key' \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "goal": "learn about music videos",
    "mode": "title_and_clean_desc"
  }'
```

## Development Notes

### Architecture (Updated Jan 2026)
- **Gemini API**: Uses Google's Gemini 2.0 Flash for video scoring and reasoning
- **Lightweight**: No local ML models to download or manage
- **Scalable**: API-based scoring with cloud infrastructure
- **Smart Caching**: Redis caching for repeated video lookups

### Configuration Management
- **Centralized Config**: All settings in `config.py`
- **Environment Variables**: Secure API key management via `.env` files
- **Multiple Environments**: Support for development, staging, and production
- **Validation**: Automatic configuration validation on startup

### Privacy and Security
- **API Key Protection**: Keys stored in environment variables, never in code
- **Secure Endpoints**: API key authentication for all endpoints
- **No Persistent Storage**: User data not stored permanently
- **Data Deletion**: Session data deleted after processing

## Troubleshooting

### Configuration Errors
If you get "Configuration errors" on startup:
```bash
# Check if .env file exists
ls -la .env

# Verify environment variables are loaded
python -c "from config import Config; print(Config.get_info())"
```

### API Key Issues
1. Verify API keys are set in `.env` file
2. Check keys are valid in respective cloud consoles
3. Test API connectivity:
```bash
curl -X GET http://localhost:8080/health
```

### Import Errors
If you get import errors, ensure all dependencies are installed:
```bash
pip install -r requirements.txt --upgrade
```

### Redis Connection Issues
Redis is optional. If Redis fails to connect:
- The app will continue working without caching
- Check Redis credentials in `.env` file
- Or disable Redis by commenting out Redis config

## License
MIT

