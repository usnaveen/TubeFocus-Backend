import os
import re
from googleapiclient.discovery import build

YT_API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not YT_API_KEY:
    raise RuntimeError("YOUTUBE_API_KEY not set in environment")

youtube = build("youtube", "v3", developerKey=YT_API_KEY)

def extract_video_id(url: str) -> str:
    """
    Parse YouTube URL to extract the 11-character video ID.
    """
    patterns = [r"v=([A-Za-z0-9_-]{11})", r"youtu\.be/([A-Za-z0-9_-]{11})"]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    raise ValueError(f"Could not extract video ID from {url}")

def fetch_metadata(video_url: str) -> tuple[str, str]:
    """
    Return (title, description) for the given YouTube video URL.
    """
    vid = extract_video_id(video_url)
    resp = youtube.videos().list(part="snippet", id=vid, maxResults=1).execute()
    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Video not found: {video_url}")
    snippet = items[0]["snippet"]
    title = snippet.get("title", "")
    desc  = snippet.get("description", "")
    return title, desc
