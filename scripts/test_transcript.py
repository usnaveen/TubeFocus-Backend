#!/usr/bin/env python3
"""
Test script for YouTube Transcript API
Run this locally to verify transcript retrieval works
"""

import sys

# Check version
try:
    import youtube_transcript_api
    print(f"✅ youtube-transcript-api version: {youtube_transcript_api.__version__}")
except AttributeError:
    print("⚠️  Could not determine youtube-transcript-api version")

print("-" * 60)

# Test 1: Import check
print("\n1. Testing imports...")
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Check if list_transcripts exists
print("\n2. Checking for list_transcripts method...")
if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
    print("✅ list_transcripts method exists")
else:
    print("❌ list_transcripts method NOT FOUND")
    print("   This is the issue! Need to update youtube-transcript-api")
    print("\n   Available methods:")
    methods = [m for m in dir(YouTubeTranscriptApi) if not m.startswith('_')]
    for method in methods:
        print(f"   - {method}")
    sys.exit(1)

# Test 3: Try to get a transcript
print("\n3. Testing transcript retrieval...")
test_video_id = "jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video
print(f"   Video ID: {test_video_id}")

try:
    # Try using list_transcripts (new API)
    transcript_list = YouTubeTranscriptApi.list_transcripts(test_video_id)
    print(f"✅ list_transcripts() works!")
    
    # Try to get English transcript
    try:
        transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        print(f"✅ Found transcript: language={transcript.language}, is_generated={transcript.is_generated}")
        
        # Fetch the actual transcript
        segments = transcript.fetch()
        print(f"✅ Fetched {len(segments)} segments")
        
        # Show first 3 segments
        print("\n   First 3 segments:")
        for seg in segments[:3]:
            print(f"   [{seg['start']:.1f}s] {seg['text']}")
            
    except NoTranscriptFound:
        print("⚠️  No English transcript found for this video")
        print("   Available languages:")
        for t in transcript_list:
            print(f"   - {t.language} (generated: {t.is_generated})")
            
except TranscriptsDisabled:
    print(f"⚠️  Transcripts are disabled for video {test_video_id}")
    print("   Try a different video ID")
    
except VideoUnavailable:
    print(f"❌ Video {test_video_id} is not available")
    
except AttributeError as e:
    print(f"❌ AttributeError: {e}")
    print("   This confirms list_transcripts doesn't exist in your version")
    print("   You need to upgrade: pip install --upgrade youtube-transcript-api")
    
except Exception as e:
    print(f"❌ Unexpected error: {type(e).__name__}: {e}")

# Test 4: Test with the old API (get_transcript)
print("\n4. Testing fallback with get_transcript (old API)...")
try:
    if hasattr(YouTubeTranscriptApi, 'get_transcript'):
        transcript = YouTubeTranscriptApi.get_transcript(test_video_id)
        print(f"✅ get_transcript() works! Got {len(transcript)} segments")
        print("   (But we need list_transcripts for language detection)")
    else:
        print("❌ get_transcript also not available")
except Exception as e:
    print(f"❌ get_transcript failed: {e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

# Final recommendation
if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
    print("✅ Your local environment is ready!")
    print("   The Cloud Run deployment might have an old version.")
    print("\n   Next steps:")
    print("   1. Verify requirements.txt has: youtube-transcript-api>=0.6.0")
    print("   2. Redeploy with: ./deploy_to_cloud_run.sh")
else:
    print("❌ Your local environment needs updating!")
    print("\n   Fix with:")
    print("   pip install --upgrade youtube-transcript-api")
    print("   # or in venv:")
    print("   source venv/bin/activate")
    print("   pip install --upgrade youtube-transcript-api")
