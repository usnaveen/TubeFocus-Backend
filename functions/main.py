from firebase_functions import https_fn, options
from firebase_admin import initialize_app
import google.generativeai as genai
import requests
import os
import json
import logging
import re

initialize_app()
logger = logging.getLogger('cloudfunctions.googleapis.com%2Fcloud-functions')

# --- CONFIGURATION (Env Vars will be set in Firebase) ---
# GOOGLE_API_KEY
# YOUTUBE_API_KEY

def get_cors_headers(origin):
    # For production, restrict this. For now, allow extensions.
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-API-KEY',
        'Access-Control-Max-Age': '3600'
    }

# --- YOUTUBE LOGIC (Ported from youtube_client.py) ---
def extract_video_id(url_or_id):
    if len(url_or_id) == 11 and not url_or_id.startswith('http'):
        return url_or_id
    patterns = [r"v=([A-Za-z0-9_-]{11})", r"youtu\.be/([A-Za-z0-9_-]{11})"]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    return None

def fetch_youtube_details(video_id):
    yt_key = os.environ.get("YOUTUBE_API_KEY")
    if not yt_key:
        logger.error("YOUTUBE_API_KEY missing")
        return None
        
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet",
        "id": video_id,
        "key": yt_key
    }
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        if not data.get("items"):
            return None
        
        snippet = data["items"][0]["snippet"]
        return {
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "tags": snippet.get("tags", []),
            "channel": snippet.get("channelTitle", "")
        }
    except Exception as e:
        logger.error(f"YouTube API Error: {e}")
        return None

# --- GEMINI LOGIC (Ported from simple_scoring.py) ---
def score_with_gemini(title, description, goal):
    gemini_key = os.environ.get("GOOGLE_API_KEY")
    if not gemini_key:
        logger.error("GOOGLE_API_KEY missing")
        raise ValueError("Server misconfiguration: Missing Gemini Key")

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt = f"""You are an expert productivity assistant.
Video Title: {title}
Video Description: {description[:1000]}...
User Goal: {goal}

Task: Rate relevance 0-100.
- 0: Irrelevant/Distracting
- 100: Highly Essential
- Provide a short reasoning.

Respond in JSON:
{{ "score": 0, "reasoning": "..." }}
"""
    try:
        response = model.generate_content(prompt)
        text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        raise e

# --- CLOUD FUNCTION ENTRY POINT ---
@https_fn.on_request(
    memory=options.MemoryOption.MB_512,
    timeout_sec=30,
)
def simple_score(req: https_fn.Request) -> https_fn.Response:
    # 1. Handle CORS
    if req.method == 'OPTIONS':
        return https_fn.Response(status=204, headers=get_cors_headers(req.headers.get("origin")))

    # 2. Setup Headers
    cors_headers = get_cors_headers(req.headers.get("origin"))
    cors_headers['Content-Type'] = 'application/json'

    # 3. Authenticate (Check Client Key)
    # The extension will send 'X-API-KEY'. We verify it matches our secret 'CLIENT_SECRET'.
    # For now, matching 'test_key' logic from dev.
    client_key = req.headers.get('X-API-KEY')
    expected_key = os.environ.get('CLIENT_API_KEY', 'test_key') 
    
    # Optional: Basic security check (can be disabled for prototype)
    if client_key != expected_key:
        return https_fn.Response(
            json.dumps({"error": "Unauthorized"}), 
            status=401, 
            headers=cors_headers
        )

    # 4. Parse Body
    try:
        data = req.get_json()
        video_url = data.get('video_url')
        goal = data.get('goal')
        
        if not video_url or not goal:
            return https_fn.Response(
                json.dumps({"error": "Missing video_url or goal"}),
                status=400,
                headers=cors_headers
            )
            
        # 5. Execute Logic
        video_id = extract_video_id(video_url)
        if not video_id:
             return https_fn.Response(json.dumps({"error": "Invalid URL"}), status=400, headers=cors_headers)

        details = fetch_youtube_details(video_id)
        if not details:
            # Fallback if API fails or video private? 
            # For now return error
            return https_fn.Response(
                json.dumps({"error": "Video not found", "debug": "YouTube API returned empty"}), 
                status=404, 
                headers=cors_headers
            )

        score_data = score_with_gemini(details['title'], details['description'], goal)
        
        # 6. Return Success
        return https_fn.Response(
            json.dumps(score_data),
            status=200,
            headers=cors_headers
        )

    except Exception as e:
        logger.error(f"Unhandled Error: {e}")
        return https_fn.Response(
            json.dumps({"error": "Internal Server Error", "details": str(e)}),
            status=500,
            headers=cors_headers
        )
