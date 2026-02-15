from google import genai
import logging
import json
import os
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
# if Config.GOOGLE_API_KEY:
#    genai.configure(api_key=Config.GOOGLE_API_KEY)

def _get_genai_score(prompt):
    if not Config.GOOGLE_API_KEY:
        logger.error("Missing GOOGLE_API_KEY")
        return 0.0

    try:
        client = genai.Client(api_key=Config.GOOGLE_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        text = response.text.strip()
        if text.startswith('```json'): # Cleanup
            text = text.replace('```json', '').replace('```', '')
        elif text.startswith('```'):
            text = text.replace('```', '')
            
        data = json.loads(text)
        # Normalize 0-100 to 0.0-1.0 as expected by detailed endpoints
        return float(data.get('score', 0)) / 100.0
    except Exception as e:
        logger.error(f"GenAI Detailed Scoring Error: {e}")
        return 0.0

# --- 1. Description Scoring ---
def score_description(goal, title, description):
    prompt = f"""Rate the relevance of the video description to the user's goal.
Video Title: {title}
Description: {description[:2000]}
User Goal: {goal}

Output JSON only with a score 0-100:
{{ "score": <0-100> }}
"""
    return _get_genai_score(prompt)

# --- 2. Title Scoring ---
def score_title(goal, title):
    prompt = f"""Rate the relevance of the video title to the user's goal.
Title: {title}
User Goal: {goal}

Output JSON only with a score 0-100:
{{ "score": <0-100> }}
"""
    return _get_genai_score(prompt)

# --- 3. Tag Scoring ---
def score_tags(goal, tags_list):
    tags_str = ", ".join(tags_list[:20])
    prompt = f"""Rate the relevance of these video tags to the user's goal.
Tags: {tags_str}
User Goal: {goal}

Output JSON only with a score 0-100:
{{ "score": <0-100> }}
"""
    return _get_genai_score(prompt)

# --- 4. Category Scoring ---
def score_category(goal, category_name):
    prompt = f"""Rate the relevance of the video category to the user's goal.
Category: {category_name}
User Goal: {goal}

Output JSON only with a score 0-100:
{{ "score": <0-100> }}
"""
    return _get_genai_score(prompt)