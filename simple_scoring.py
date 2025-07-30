# simple_scoring.py
# Simplified scoring using 5 sentence transformers (similar to Docker container approach)

from sentence_transformers import SentenceTransformer, util
import torch
from youtube_scraper import fetch_metadata
import os
import re
import nltk
from nltk.tokenize import sent_tokenize
import logging

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    try:
        nltk.download('punkt')
    except:
        print("⚠️  NLTK download failed, using fallback sentence splitting")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MIN_SENTENCE_LENGTH = 8  # Minimum sentence length for cleaning

# --- Text Cleaning Functions ---
def clean_text_basic(text: str) -> str:
    """Basic text cleaning without over-filtering."""
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove excessive punctuation
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)
    text = re.sub(r'[.]{3,}', '...', text)
    return text.strip()

def extract_meaningful_content(description: str) -> str:
    """
    Extract meaningful content from description with minimal filtering.
    The key insight: Don't over-filter! Let the semantic models decide relevance.
    """
    if not description.strip():
        return ""

    # Split into sentences
    try:
        sentences = sent_tokenize(description)
    except:
        # Fallback splitting
        sentences = re.split(r'[.!?]+', description)

    meaningful_sentences = []

    for sentence in sentences:
        cleaned = clean_text_basic(sentence)

        # Only filter out obvious junk
        if (len(cleaned) < MIN_SENTENCE_LENGTH or
            re.match(r'^[\W\d]*$', cleaned) or  # Only symbols/numbers
            cleaned.lower() in ['', 'n/a', 'none', 'null']):
            continue

        # Keep URLs if they seem educational (e.g., course links)
        if 'http' in cleaned.lower():
            if any(edu_term in cleaned.lower() for edu_term in
                   ['course', 'lecture', 'edu', 'mit', 'stanford', 'university', 'tutorial']):
                meaningful_sentences.append(cleaned)
            # Skip other URLs
            continue

        # Keep everything else - let semantic scoring decide relevance
        meaningful_sentences.append(cleaned)

    logger.info(f"Extracted {len(meaningful_sentences)} meaningful sentences from description")
    return " ".join(meaningful_sentences)

# Define the paths to the 5 sentence transformer models
SIMPLE_MODEL_PATHS = [
    "models/sentence-transformers_all-MiniLM-L6-v2",
    "models/sentence-transformers_multi-qa-MiniLM-L6-cos-v1",
    "models/sentence-transformers_paraphrase-MiniLM-L3-v2",
    "models/sentence-transformers_all-mpnet-base-v2",
    "models/sentence-transformers_all-distilroberta-v1"
]

# Load all models from the local paths just once when the application starts
try:
    print("Loading simple scoring models from local directories...")
    simple_models = {
        path: SentenceTransformer(path)
        for path in SIMPLE_MODEL_PATHS
    }
    print(f"Successfully loaded {len(simple_models)} simple scoring models.")
except Exception as e:
    print(f"FATAL: Error loading simple scoring models: {e}")
    simple_models = {}


def _calculate_simple_score_from_text(text_to_embed: str, goal: str) -> int:
    """
    Computes embeddings for the given text and goal, calculates their
    cosine similarity, and returns a score from 0 to 100.
    Uses the same approach as the Docker container.
    """
    if not simple_models:
        raise RuntimeError("Simple scoring models are not loaded, cannot compute score.")

    scores = []
    for model_name, model in simple_models.items():
        vec_text = model.encode(text_to_embed, convert_to_tensor=True)
        vec_goal = model.encode(goal, convert_to_tensor=True)
        cos_sim = util.cos_sim(vec_text, vec_goal).item()
        pct_score = max(0, min(100, int((cos_sim + 1) * 50)))
        scores.append(pct_score)

    if not scores:
        return 0
    
    return int(round(sum(scores) / len(scores)))


def compute_simple_score(video_url: str, goal: str) -> int:
    """
    Fetches video metadata (title and description) and calculates a
    relevance score based on the provided goal using simplified approach.
    """
    title, desc = fetch_metadata(video_url)
    text_to_embed = f"{title}\n\n{desc}"
    final_score = _calculate_simple_score_from_text(text_to_embed, goal)
    print(f"Simple Score - URL: {video_url}, Goal: '{goal}', Final Score: {final_score}")
    return final_score


def compute_simple_score_from_title(video_url: str, goal: str) -> int:
    """
    Fetches video metadata (title only) and calculates a relevance score
    based on the provided goal using simplified approach.
    """
    title, _ = fetch_metadata(video_url)
    final_score = _calculate_simple_score_from_text(title, goal)
    print(f"Simple Title Score - URL: {video_url}, Goal: '{goal}', Title-Only Score: {final_score}")
    return final_score


def compute_simple_score_title_and_clean_desc(video_url: str, goal: str) -> int:
    """
    Fetches video metadata (title and cleaned description) and calculates a relevance score
    based on the provided goal using simplified approach.
    """
    title, desc = fetch_metadata(video_url)
    cleaned_desc = extract_meaningful_content(desc)
    text_to_embed = f"{title}. {cleaned_desc}" if cleaned_desc else title
    final_score = _calculate_simple_score_from_text(text_to_embed, goal)
    print(f"Simple Title+CleanDesc Score - URL: {video_url}, Goal: '{goal}', Score: {final_score}")
    return final_score 