# Simple Title/Description Endpoint

## Overview

The `/simpletitledesc` endpoint provides a simplified scoring approach using 5 sentence transformers, similar to the Docker container implementation. This endpoint offers two modes: title-only scoring and title+description scoring.

## Endpoint Details

**URL:** `/simpletitledesc`  
**Method:** POST  
**Authentication:** Required (X-API-KEY header)

## Request Format

```json
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "goal": "your learning goal",
  "mode": "title_and_description"  // or "title_only"
}
```

### Parameters

- **video_url** (required): Full YouTube video URL
- **goal** (required): Your learning goal (2-200 characters)
- **mode** (optional): Scoring mode
  - `"title_and_description"` (default): Uses both title and description
  - `"title_only"`: Uses only the video title
  - `"title_and_clean_desc"`: Uses title and cleaned description (filters out noise)

## Response Format

```json
{
  "score": 75,
  "mode": "title_and_description"
}
```

### Response Fields

- **score**: Integer score from 0-100 indicating relevance
- **mode**: The scoring mode used

## Example Usage

### cURL Example

```bash
curl -X POST http://localhost:5001/simpletitledesc \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_api_key" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "goal": "learn programming",
    "mode": "title_and_clean_desc"
  }'
```

### Python Example

```python
import requests

response = requests.post(
    "http://localhost:5001/simpletitledesc",
    headers={
        "Content-Type": "application/json",
        "X-API-KEY": "your_api_key"
    },
    json={
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "goal": "learn programming",
        "mode": "title_and_description"
    }
)

result = response.json()
print(f"Score: {result['score']}")
```

## Technical Details

### Models Used

The endpoint uses 5 sentence transformer models:
1. `sentence-transformers_all-MiniLM-L6-v2`
2. `sentence-transformers_multi-qa-MiniLM-L6-cos-v1`
3. `sentence-transformers_paraphrase-MiniLM-L3-v2`
4. `sentence-transformers_all-mpnet-base-v2`
5. `sentence-transformers_all-distilroberta-v1`

### Scoring Algorithm

1. **Text Processing**: Extracts title and/or description from YouTube video
2. **Embedding Generation**: Creates embeddings for both video content and goal using all 5 models
3. **Similarity Calculation**: Computes cosine similarity between embeddings
4. **Score Aggregation**: Averages scores from all models and converts to 0-100 scale

### Differences from Advanced Endpoint

- **Simpler approach**: No cross-encoders or zero-shot classification
- **Faster processing**: Uses only embedding similarity
- **Consistent with Docker container**: Same algorithm as production container
- **No machine learning**: Pure rule-based scoring
- **Text cleaning**: The `title_and_clean_desc` mode filters out noise from descriptions

## Error Handling

The endpoint returns appropriate HTTP status codes:

- **200**: Success
- **400**: Invalid parameters (missing video_url, goal, or invalid mode)
- **401**: Missing or invalid API key
- **500**: Internal server error

### Mode Comparison

| Mode | Description | Use Case |
|------|-------------|----------|
| `title_only` | Uses only video title | Fastest, good for quick assessments |
| `title_and_description` | Uses title + full description | Most comprehensive, includes all metadata |
| `title_and_clean_desc` | Uses title + cleaned description | Balanced, filters out noise while keeping relevant content |

## Testing

Run the test script to verify the endpoint:

```bash
python test_simple_endpoint.py
```

## Comparison with Docker Container

This endpoint implements the same scoring approach as the Docker container:
- Same 5 sentence transformer models
- Same cosine similarity calculation
- Same 0-100 scoring scale
- Same title-only and title+description modes

The main difference is that this endpoint is integrated into the development container's API alongside the more advanced scoring methods. 