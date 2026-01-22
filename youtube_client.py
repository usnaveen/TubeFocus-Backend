import os
import re
import json
import requests
# import redis
from config import Config, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_USERNAME, CACHE_TTL_SECONDS

YOUTUBE_VIDEO_URL = 'https://www.googleapis.com/youtube/v3/videos'
YOUTUBE_CATEGORY_URL = 'https://www.googleapis.com/youtube/v3/videoCategories'

redis_client = None # Initialize to None

def initialize_redis_client():
    return None
    # global redis_client
    # if redis_client is not None: # Already initialized
    #     return redis_client
    # try:
    #     client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, username=REDIS_USERNAME, password=REDIS_PASSWORD, ssl=False, decode_responses=True)
    #     client.ping()
    #     print("Successfully connected to Redis.")
    #     redis_client = client
    #     return client
    # except redis.exceptions.ConnectionError as e:
    #     print(f"Could not connect to Redis: {e}")
    #     redis_client = None
    #     return None

# Initialize Redis client when the module is imported
# initialize_redis_client()

def extract_video_id(url_or_id: str) -> str:
    """
    Parse YouTube URL to extract the 11-character video ID.
    If an 11-character string is passed, it is assumed to be a video ID.
    """
    if len(url_or_id) == 11 and not url_or_id.startswith('http'):
        return url_or_id
    patterns = [r"v=([A-Za-z0-9_-]{11})", r"youtu\.be/([A-Za-z0-9_-]{11})"]
    for pat in patterns:
        m = re.search(pat, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract video ID from {url_or_id}")

def get_video_details(video_url_or_id: str):
    video_id = extract_video_id(video_url_or_id)
    cache_key = f"youtube:video_details:{video_id}"

    # Check cache first
    if redis_client:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            print(f"Cache hit for video details {video_id}")
            return json.loads(cached_data)

    print(f"Cache miss for video details {video_id}, fetching from API.")
    params = {
        'part': 'snippet',
        'id': video_id,
        'key': Config.YOUTUBE_API_KEY
    }
    resp = requests.get(YOUTUBE_VIDEO_URL, params=params)
    data = resp.json()
    if not data.get('items') or not data['items'][0]:
        return None
    snippet = data['items'][0]['snippet']
    category_id = snippet.get('categoryId', '')
    category_name = get_category_name(category_id) if category_id else ''
    details = {
        'title': snippet.get('title', ''),
        'description': snippet.get('description', ''),
        'tags': snippet.get('tags', []),
        'category': category_name
    }

    # Store in cache
    if redis_client:
        data_to_cache = json.dumps(details)
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, data_to_cache)

    return details

def get_category_name(category_id: str):
    cache_key = f"youtube:category_name:{category_id}"

    # Check cache first
    if redis_client:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            print(f"Cache hit for category {category_id}")
            return json.loads(cached_data)

    print(f"Cache miss for category {category_id}, fetching from API.")
    params = {
        'part': 'snippet',
        'id': category_id,
        'key': Config.YOUTUBE_API_KEY
    }
    resp = requests.get(YOUTUBE_CATEGORY_URL, params=params)
    data = resp.json()
    if not data.get('items') or not data['items'][0]:
        return ''
    category_name = data['items'][0]['snippet']['title']

    # Store in cache
    if redis_client:
        data_to_cache = json.dumps(category_name)
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, data_to_cache)

    return category_name
