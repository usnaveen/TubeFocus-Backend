print("Starting verification script...")
import sys
import os
print("Importing os/sys done")
import logging
from unittest.mock import MagicMock

# Mock environment
os.environ['GOOGLE_API_KEY'] = 'test_key' 
# Mock Redis in youtube_client to prevent connection attempt on import
sys.modules['redis'] = MagicMock()
import youtube_client
youtube_client.redis_client = None

# Mock google.generativeai
sys.modules['google'] = MagicMock()
sys.modules['google.generativeai'] = MagicMock()

from simple_scoring import _get_scoring_prompt, compute_simple_score 

def test_prompt_generation():
    print("Testing prompt generation...")
    title = "Test Video"
    desc = "Test Description"
    goal = "Learn Python"
    transcript = "This is a transcript about Python programming."
    
    prompt = _get_scoring_prompt(title, desc, goal, transcript)
    
    if "Video Transcript (excerpt):" in prompt and transcript in prompt:
        print("PASS: Transcript included in prompt.")
    else:
        print("FAIL: Transcript MISSING from prompt.")
        print("Prompt content:\n", prompt)

def test_compute_signature():
    # Just checking if the function accepts the argument without error
    # We can't actually call it without a valid API key and internet
    import inspect
    sig = inspect.signature(compute_simple_score)
    if 'transcript' in sig.parameters:
        print("PASS: compute_simple_score accepts 'transcript'.")
    else:
        print("FAIL: compute_simple_score signature incorrect.")

if __name__ == "__main__":
    test_prompt_generation()
    test_compute_signature()
