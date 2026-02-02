import os
from google import genai
import logging
import json
from youtube_client import get_video_details
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure API
if not Config.GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables. Scoring will fail.")

def _get_scoring_prompt(title, description, goal, transcript=""):
    transcript_section = ""
    if transcript:
        # We limit transcript to ~2000 chars to avoid hitting token limits while keeping context
        transcript_section = f"\n\nVideo Transcript (excerpt):\n{transcript[:2000]}..."

    return f"""You are an expert productivity assistant helping a user decide if a YouTube video is worth watching based on their specific goal.

Video Title: {title}
Video Description: {description[:1000]}... (truncated){transcript_section}

User's Goal: {goal}

Task: Rate the relevance of this video to the user's goal on a scale of 0 to 100. 
- 0 means completely irrelevant.
- 100 means perfectly aligned and essential.
- Consider if the video actually teaches what is needed or just discusses it.
- If the title is vague but the transcript confirms relevance, score high.
- If the title is clickbait and transcript is irrelevant, score low.

Respond with valid JSON only:
{{
  "score": <integer_0_to_100>,
  "reasoning": "<short_explanation>"
}}
"""

def compute_simple_score(video_url: str, goal: str, transcript: str = "") -> tuple:
    """
    Scores a video using Google's Gemini API.
    Returns: (score, reasoning, debug_info)
    """
    if not Config.GOOGLE_API_KEY:
        logger.error("Attempted to score without GOOGLE_API_KEY")
        raise RuntimeError("GOOGLE_API_KEY is missing. Please set it in your environment.")

    # Fetch details
    details = get_video_details(video_url)
    if not details:
        raise ValueError(f"Could not retrieve details for video {video_url}")
    
    title = details.get('title', '')
    description = details.get('description', '')

    # --- Debug Info Return ---
    # FIXED: Use details.get('id') instead of undefined video_id
    debug_info = {
         'youtube_api': {
             'status': 'success' if title else 'failed',
             'video_id': details.get('id', 'unknown'), 
             'title': title,
             'description_length': len(description),
             'transcript_length': len(transcript)
         },
         'gemini_api': {
             'model': 'gemini-2.0-flash',
             'status': 'pending'
         }
    }

    try:
        current_key = Config.GOOGLE_API_KEY or 'NONE'
        logger.info(f"DEBUG: Using Google API Key: {current_key[:10]}..." if current_key != 'NONE' else "DEBUG: No API key configured")
        
        client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        prompt = _get_scoring_prompt(title, description, goal, transcript)
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        
        # Parse JSON from response
        text_response = response.text.strip()
        # Handle potential markdown wrapping
        if text_response.startswith('```json'):
            text_response = text_response.replace('```json', '').replace('```', '')
        elif text_response.startswith('```'):
             text_response = text_response.replace('```', '')

        result = json.loads(text_response)
        score = int(result.get('score', 0))
        reasoning = result.get('reasoning', '')
        
        logger.info(f"Scored {video_url} against '{goal}': {score} (Reason: {reasoning})")
        debug_info['gemini_api']['status'] = 'success'
        debug_info['gemini_api']['raw_response'] = text_response
        
        return score, reasoning, debug_info
        
    except Exception as e:
        debug_info['gemini_api']['status'] = 'failed'
        debug_info['gemini_api']['error'] = str(e)
        logger.error(f"GenAI Scoring failed: {e}")
        # Attach debug info to exception so api.py can retrieve it
        e.debug_info = debug_info
        raise e

# Compatibility aliases - these just call the main function and ignore extra returns if not needed
# But api.py expects them to return (score) or (score, reasoning, debug) depending on usage.
# To be safe, let's make them return the full tuple since we updated api.py to handle it for the main path.
# Actually, looking at api.py, it only unpacks the main function call. The alias calls are inside specific 'if mode ==' blocks.
# We should probably update them to match signature or update api.py. 
# For now, let's keep them returning just score if that's what legacy expected, 
# BUT api.py logic for "title_only" etc might break if it expects a tuple now?
# Checking api.py content from memory/logs:
# if mode == "title_only": score = ...; debug_info = {}
# So these functions should return just valid score/int.

def compute_simple_score_from_title(video_url: str, goal: str) -> int:
    score, _, _ = compute_simple_score(video_url, goal)
    return score

def compute_simple_score_title_and_clean_desc(video_url: str, goal: str) -> int:
    score, _, _ = compute_simple_score(video_url, goal)
    return score