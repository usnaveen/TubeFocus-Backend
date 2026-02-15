import os
import google.generativeai as genai
from youtube_client import get_video_details
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

print("="*40)
print("     API DIAGNOSTIC TOOL")
print("="*40)

# 1. Test YouTube API
print("\n[1/2] Testing YouTube API...")
YOUTUBE_KEY = os.environ.get('YOUTUBE_API_KEY')
print(f"Key loaded: {YOUTUBE_KEY[:10]}..." if YOUTUBE_KEY else "Key loaded: NONE")

try:
    # Test video: "Official YouTube Blog" or similar unrelated video
    TEST_VIDEO_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw" 
    details = get_video_details(TEST_VIDEO_URL)
    
    if details and details.get('title'):
        print(f"SUCCESS! Found video: '{details['title']}'")
    else:
        print("FAILURE! API call returned no details (or empty).")
except Exception as e:
    print(f"FAILURE! Exception: {e}")


# 2. Test Gemini API
print("\n[2/2] Testing Gemini API...")
GOOGLE_KEY = os.environ.get('GOOGLE_API_KEY')
print(f"Key loaded: {GOOGLE_KEY[:10]}..." if GOOGLE_KEY else "Key loaded: NONE")

try:
    if not GOOGLE_KEY:
        raise ValueError("No Google API Key found in environment.")
        
    genai.configure(api_key=GOOGLE_KEY)
    
    # Try gemini-2.0-flash since that's what we pivoted to
    model = genai.GenerativeModel('gemini-2.0-flash')
    print("Sending prompt: 'Reply with the word OK'")
    response = model.generate_content("Reply with the word OK")
    
    if response and response.text:
       print(f"SUCCESS! Response: '{response.text.strip()}'")
    else:
       print("FAILURE! Empty response from Gemini.")

except Exception as e:
    print(f"FAILURE! Exception: {e}")

print("\n" + "="*40)
