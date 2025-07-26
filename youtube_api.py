import os
import requests
from functools import lru_cache

YT_API_KEY = os.environ.get('YOUTUBE_API_KEY')

YOUTUBE_VIDEO_URL = 'https://www.googleapis.com/youtube/v3/videos'
YOUTUBE_CATEGORY_URL = 'https://www.googleapis.com/youtube/v3/videoCategories'

@lru_cache(maxsize=256)
def fetch_video_details(video_id):
    params = {
        'part': 'snippet',
        'id': video_id,
        'key': YT_API_KEY
    }
    resp = requests.get(YOUTUBE_VIDEO_URL, params=params)
    data = resp.json()
    if not data.get('items') or not data['items'][0]:
        return None
    snippet = data['items'][0]['snippet']
    category_id = snippet.get('categoryId', '')
    category_name = fetch_category_name(category_id) if category_id else ''
    return {
        'title': snippet.get('title', ''),
        'description': snippet.get('description', ''),
        'tags': tuple(snippet.get('tags', [])),  # lru_cache requires hashable types
        'category': category_name
    }

@lru_cache(maxsize=64)
def fetch_category_name(category_id):
    params = {
        'part': 'snippet',
        'id': category_id,
        'key': YT_API_KEY
    }
    resp = requests.get(YOUTUBE_CATEGORY_URL, params=params)
    data = resp.json()
    if not data.get('items') or not data['items'][0]:
        return ''
    return data['items'][0]['snippet']['title'] 