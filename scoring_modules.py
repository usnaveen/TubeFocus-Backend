import google.generativeai as genai
import logging
import json
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Re-use the key from environment
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

def _get_genai_score(prompt):
    if not GOOGLE_API_KEY:
        logger.error("Missing GOOGLE_API_KEY")
        return 0.0

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
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