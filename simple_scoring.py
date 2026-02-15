import os
from google import genai
import logging
import json
import re
from youtube_client import get_video_details
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure API
if not Config.GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY not found in environment variables. Scoring will fail.")

def _get_scoring_prompt(title, description, goal, intent=None, transcript=""):
    transcript_section = ""
    if transcript:
        # We limit transcript to ~2000 chars to avoid hitting token limits while keeping context
        transcript_section = f"\n\nVideo Transcript (excerpt):\n{transcript[:2000]}..."

    intent_section = ""
    if intent:
         intent_section = f"""
User Intent: {intent.get('intent', 'General Learning')}
Constraints: {intent.get('constraints', '')}
Note: Use constraints as guidance. Do not over-penalize adjacent technical topics.
"""

    return f"""You are an expert productivity assistant helping a user decide if a YouTube video is worth watching based on their specific goal.

Video Title: {title}
Video Description: {description[:1000]}... (truncated){transcript_section}

User's Goal: {goal}
{intent_section}

Task: Rate the relevance of this video to the user's goal on a scale of 0 to 100. 
- 0 means completely irrelevant.
- 100 means perfectly aligned and essential.
- Consider if the video actually teaches what is needed or just discusses it.
- If the title is vague but the transcript confirms relevance, score high.
- If the title is clickbait and transcript is irrelevant, score low.
- Penalize entertainment/tangents, but keep technically adjacent topics in a fair medium score range.

Respond with valid JSON only:
{{
  "score": <integer_0_to_100>,
  "reasoning": "<short_explanation>"
}}
"""

def _normalize_tokens(text: str) -> list:
    return [t for t in re.split(r'[^a-z0-9]+', (text or '').lower()) if len(t) > 2]

def _is_ai_ml_goal(goal: str) -> bool:
    goal_text = (goal or '').lower()
    keywords = [
        'deep learning', 'machine learning', 'ml', 'artificial intelligence', 'ai',
        'llm', 'transformer', 'neural network', 'interview'
    ]
    return any(k in goal_text for k in keywords)

def _is_ai_ml_video_topic(title: str, description: str, transcript: str = '') -> bool:
    text = f"{title} {description} {transcript[:2000]}".lower()
    keywords = [
        'kv cache', 'key value cache', 'transformer', 'attention', 'llm',
        'inference', 'token', 'decoder', 'prompt caching', 'rag',
        'embedding', 'fine tuning', 'quantization', 'neural network', 'deep learning'
    ]
    return any(k in text for k in keywords)

def _goal_overlap_ratio(goal: str, title: str, description: str) -> float:
    stopwords = {
        'the', 'and', 'for', 'with', 'from', 'that', 'this', 'what', 'when', 'where',
        'why', 'how', 'learn', 'learning', 'video', 'videos', 'about', 'into'
    }
    goal_tokens = [t for t in _normalize_tokens(goal) if t not in stopwords]
    if not goal_tokens:
        return 0.0
    video_tokens = set(_normalize_tokens(f"{title} {description[:1200]}"))
    overlap = sum(1 for t in goal_tokens if t in video_tokens)
    return overlap / len(goal_tokens)

def _postprocess_score(score: int, goal: str, title: str, description: str, transcript: str = "") -> tuple:
    adjusted = int(score)
    adjustments = []

    overlap_ratio = _goal_overlap_ratio(goal, title, description)
    ai_goal = _is_ai_ml_goal(goal)
    ai_video = _is_ai_ml_video_topic(title, description, transcript)

    # Avoid harsh under-scoring for clearly related technical topics.
    if ai_goal and ai_video and adjusted < 58:
        adjusted = 58
        adjustments.append('ai_ml_topic_floor_58')

    if overlap_ratio >= 0.35 and adjusted < 60:
        adjusted = 60
        adjustments.append('goal_overlap_floor_60')

    # Interview prep should still allow deep technical adjacent concepts.
    goal_text = (goal or '').lower()
    if 'interview' in goal_text and ai_video and adjusted < 62:
        adjusted = 62
        adjustments.append('interview_adjacent_topic_floor_62')

    adjusted = max(0, min(100, adjusted))
    return adjusted, {
        'overlap_ratio': round(overlap_ratio, 3),
        'ai_ml_goal': ai_goal,
        'ai_ml_video_topic': ai_video,
        'adjustments': adjustments
    }

def compute_simple_score(video_url: str, goal: str, transcript: str = "", intent=None, blocked_channels=None, video_details=None) -> tuple:
    """
    Scores a video using Google's Gemini API, respecting Intent and Channel Blocks.
    Returns: (score, reasoning, debug_info)
    """
    if not Config.GOOGLE_API_KEY:
        logger.error("Attempted to score without GOOGLE_API_KEY")
        raise RuntimeError("GOOGLE_API_KEY is missing. Please set it in your environment.")

    # Fetch details if not provided
    details = video_details if video_details else get_video_details(video_url)
    if not details:
        raise ValueError(f"Could not retrieve details for video {video_url}")
    
    title = details.get('title', '')
    description = details.get('description', '')
    channel_title = details.get('channelTitle', '')
    category_id = details.get('categoryId') # Need to ensure youtube_client returns this

    # --- 1. Fast Block Checks ---
    # Channel Block
    if blocked_channels and channel_title in blocked_channels:
        return 0, f"Blocked Channel: {channel_title}", {'status': 'blocked', 'reason': 'channel_block'}

    # Category Block
    # 10=Music, 20=Gaming, 23=Comedy, 24=Entertainment
    BANNED_CATEGORIES = ['10', '20', '23', '24']
    ignored_categories = set(BANNED_CATEGORIES)
    
    if intent:
         if intent.get('intent') == 'Infotainment/Chill':
             ignored_categories = {'10'} 
         elif intent.get('intent') == 'Game Dev' or 'Game' in goal:
             ignored_categories.discard('20')

    if category_id and str(category_id) in ignored_categories:
        return 5, f"Distracting Category ({category_id}) for {intent.get('intent') if intent else 'current goal'}", {'status': 'blocked', 'reason': 'category_block'}


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
        client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        prompt = _get_scoring_prompt(title, description, goal, intent, transcript)
        
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
        score, score_adjustment_info = _postprocess_score(
            score=score,
            goal=goal,
            title=title,
            description=description,
            transcript=transcript
        )
        
        logger.info(f"Scored {video_url} against '{goal}': {score} (Reason: {reasoning})")
        debug_info['gemini_api']['status'] = 'success'
        debug_info['gemini_api']['raw_response'] = text_response
        debug_info['post_processing'] = score_adjustment_info
        
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
