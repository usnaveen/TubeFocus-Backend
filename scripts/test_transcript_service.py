#!/usr/bin/env python3
"""
Test the transcript_service.py module directly
This tests the exact code used by the API
"""

import sys
import os

print("=" * 60)
print("Testing transcript_service.py")
print("=" * 60)

# Test import
print("\n1. Importing transcript_service...")
try:
    from transcript_service import get_transcript, get_transcript_excerpt, extract_video_id
    print("✅ Import successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test video IDs
test_videos = [
    ("jNQXAC9IVRw", "Me at the zoo (first YouTube video)"),
    ("dQw4w9WgXcQ", "Rick Astley - Never Gonna Give You Up"),
    ("9bZkp7q19f0", "PSY - GANGNAM STYLE"),
]

print("\n2. Testing extract_video_id...")
test_urls = [
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",
    "https://youtu.be/jNQXAC9IVRw",
    "jNQXAC9IVRw",
]
for url in test_urls:
    try:
        vid_id = extract_video_id(url)
        print(f"✅ {url[:40]:40} -> {vid_id}")
    except Exception as e:
        print(f"❌ {url} -> Error: {e}")

print("\n3. Testing get_transcript_excerpt...")
for video_id, description in test_videos:
    print(f"\n   Testing: {description}")
    print(f"   Video ID: {video_id}")
    
    try:
        result = get_transcript_excerpt(video_id, max_length=500)
        
        if result.get('error'):
            print(f"   ⚠️  Error: {result['error']}")
        else:
            transcript = result.get('transcript', '')
            language = result.get('language', 'unknown')
            is_generated = result.get('is_generated', False)
            segments = result.get('segments', [])
            
            print(f"   ✅ Success!")
            print(f"   Language: {language}")
            print(f"   Is Generated: {is_generated}")
            print(f"   Segments: {len(segments)}")
            print(f"   Transcript length: {len(transcript)} chars")
            print(f"   Preview: {transcript[:200]}...")
            
    except Exception as e:
        print(f"   ❌ Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

print("\n4. Testing get_transcript (full)...")
try:
    result = get_transcript("jNQXAC9IVRw")
    if result.get('error'):
        print(f"❌ Error: {result['error']}")
    else:
        print(f"✅ Full transcript retrieved!")
        print(f"   Length: {len(result.get('transcript', ''))} chars")
        print(f"   Segments: {len(result.get('segments', []))}")
except Exception as e:
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNOSIS")
print("=" * 60)

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    
    if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
        print("✅ Your transcript_service.py should work!")
        print("   The API error must be from Cloud Run having old packages.")
        print("\n   Solutions:")
        print("   1. Check requirements.txt has: youtube-transcript-api>=0.6.0")
        print("   2. Delete old Cloud Run service and redeploy fresh:")
        print("      gcloud run services delete yt-scorer-api --region=us-central1")
        print("      ./deploy_to_cloud_run.sh")
    else:
        print("❌ list_transcripts not found!")
        print("   Current version is too old.")
        print("\n   Fix:")
        print("   pip install --upgrade youtube-transcript-api")
        
except Exception as e:
    print(f"❌ Could not check: {e}")

print("\n" + "=" * 60)
