import functions_framework
import google.generativeai as genai
import requests
import os
import json
import logging
import re

logger = logging.getLogger()

# Note: For Cloud Functions, environment variables are loaded directly from function configuration
# We don't use the config.py module here to keep the function self-contained

# --- HELPER: CORS HEADERS ---
def get_cors_headers(origin):
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-API-KEY',
        'Access-Control-Max-Age': '3600'
    }

# --- HELPER: YOUTUBE ---
def get_video_id(url):
    if len(url) == 11 and not url.startswith('http'): return url
    m = re.search(r"v=([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None

def get_yt_details(video_id):
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key: return None
    url = "https://www.googleapis.com/youtube/v3/videos"
    try:
        r = requests.get(url, params={"part": "snippet", "id": video_id, "key": key})
        items = r.json().get("items", [])
        if not items: return None
        s = items[0]["snippet"]
        return {"title": s["title"], "desc": s["description"]}
    except:
        return None

# --- HELPER: GEMINI ---
def score_gemini(title, desc, goal):
    key = os.environ.get("GOOGLE_API_KEY")
    if not key: return {"error": "Missing API Key"}
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""Rate 0-100 relevance.
Video: {title}
Desc: {desc[:500]}
Goal: {goal}
JSON Output: {{ "score": 0, "reasoning": "..." }} """
    try:
        resp = model.generate_content(prompt)
        # Clean markdown if present
        txt = resp.text.replace('```json', '').replace('```', '').strip()
        return json.loads(txt)
    except Exception as e:
        return {"error": str(e)}

# --- MAIN ENTRY POINT ---
@functions_framework.http
def simple_score(request):
    # 1. CORS Pre-flight
    if request.method == 'OPTIONS':
        return ('', 204, get_cors_headers(request.headers.get("origin")))

    headers = get_cors_headers(request.headers.get("origin"))
    headers['Content-Type'] = 'application/json'

    # 2. Auth Check
    client_key = request.headers.get('X-API-KEY')
    # Default to 'test_key' if env var not set
    expected = os.environ.get('CLIENT_API_KEY', 'test_key') 
    if client_key != expected:
        return (json.dumps({"error": "Unauthorized"}), 401, headers)

    # 3. Parse Request
    try:
        data = request.get_json(silent=True)
        if not data or 'video_url' not in data:
            return (json.dumps({"error": "Missing video_url"}), 400, headers)
            
        vid = get_video_id(data['video_url'])
        if not vid:
             return (json.dumps({"error": "Invalid URL"}), 400, headers)

        # 4. Run Logic
        details = get_yt_details(vid)
        if not details:
            # Fallback mock for debugging if YT fails
            details = {"title": "Unknown Video", "desc": "No description"}
        
        result = score_gemini(details['title'], details['desc'], data.get('goal', 'General'))
        # Merge metadata into response so frontend doesn't need its own API Key
        result['title'] = details['title']
        result['description'] = details['desc']
        return (json.dumps(result), 200, headers)

    except Exception as e:
        return (json.dumps({"error": str(e)}), 500, headers)
