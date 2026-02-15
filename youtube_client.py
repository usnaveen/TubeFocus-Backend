import os
import re
import json
import requests
from config import Config

YOUTUBE_VIDEO_URL = 'https://www.googleapis.com/youtube/v3/videos'
YOUTUBE_CATEGORY_URL = 'https://www.googleapis.com/youtube/v3/videoCategories'
YOUTUBE_COMMENT_THREADS_URL = 'https://www.googleapis.com/youtube/v3/commentThreads'

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
    
    # Direct API fetch - No caching (Redis removed)
    print(f"Fetching video details from API for {video_id}")
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

    return details

def get_category_name(category_id: str):
    # Direct API fetch - No caching (Redis removed)
    print(f"Fetching category name from API for {category_id}")
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

    return category_name

def get_video_comments(video_url_or_id: str, max_results: int = 20):
    """
    Fetch top comments for a video.
    Returns a list of comment text snippets.
    """
    try:
        video_id = extract_video_id(video_url_or_id)
        print(f"Fetching comments from API for {video_id}")
        
        params = {
            'part': 'snippet',
            'videoId': video_id,
            'maxResults': max_results,
            'order': 'relevance',  # Get top comments
            'textFormat': 'plainText',
            'key': Config.YOUTUBE_API_KEY
        }
        
        resp = requests.get(YOUTUBE_COMMENT_THREADS_URL, params=params)
        
        if resp.status_code != 200:
            print(f"Error fetching comments: {resp.status_code} - {resp.text}")
            return []
            
        data = resp.json()
        comments = []
        
        if 'items' in data:
            for item in data['items']:
                comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                comments.append(comment)
                
        return comments
        
    except Exception as e:
        print(f"Failed to get comments: {e}")
        return []
