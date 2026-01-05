import os
import google.generativeai as genai
import logging
import json
from youtube_client import get_video_details

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure API
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    logger.warning("GOOGLE_API_KEY not found in environment variables. Scoring will fail.")

def _get_scoring_prompt(title, description, goal):
    return f"""You are an expert productivity assistant helping a user decide if a YouTube video is worth watching based on their specific goal.

Video Title: {title}
Video Description: {description[:1000]}... (truncated)

User's Goal: {goal}

Task: Rate the relevance of this video to the user's goal on a scale of 0 to 100. 
- 0 means completely irrelevant.
- 100 means perfectly aligned and essential.
- Consider if the video actually teaches what is needed or just discusses it.

Respond with valid JSON only:
{{
  "score": <integer_0_to_100>,
  "reasoning": "<short_explanation>"
}}
"""

def compute_simple_score(video_url: str, goal: str) -> int:
    """
    Scores a video using Google's Gemini API.
    """
    if not GOOGLE_API_KEY:
        logger.error("Attempted to score without GOOGLE_API_KEY")
        raise RuntimeError("GOOGLE_API_KEY is missing. Please set it in your environment.")

    # Fetch details
    details = get_video_details(video_url)
    if not details:
        raise ValueError(f"Could not retrieve details for video {video_url}")
    
    title = details.get('title', '')
    description = details.get('description', '')

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = _get_scoring_prompt(title, description, goal)
        
        response = model.generate_content(prompt)
        
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
        return score

    except Exception as e:
        logger.error(f"GenAI Scoring failed: {e}")
        # Fallback or re-raise? For now re-raise as we want to know if it fails.
        raise e

# Compatibility aliases
def compute_simple_score_from_title(video_url: str, goal: str) -> int:
    return compute_simple_score(video_url, goal)

def compute_simple_score_title_and_clean_desc(video_url: str, goal: str) -> int:
    return compute_simple_score(video_url, goal)