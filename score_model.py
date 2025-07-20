# score_model.py (Updated for Local Caching)

from sentence_transformers import SentenceTransformer, util
import torch
from youtube_scraper import fetch_metadata
import os

# 1. Define the paths to your locally downloaded models
# These paths must match the folder names inside your 'models' directory.
MODEL_PATHS = [
    "models/sentence-transformers_all-MiniLM-L6-v2",
    "models/sentence-transformers_multi-qa-MiniLM-L6-cos-v1",
    "models/sentence-transformers_paraphrase-MiniLM-L3-v2",
    "models/sentence-transformers_all-mpnet-base-v2",
    "models/sentence-transformers_all-distilroberta-v1"
]

# 2. Load all models from the local paths just once when the application starts.
# This is much more efficient than loading them on every request.
try:
    print("Loading models from local directories...")
    models = {
        path: SentenceTransformer(path)
        for path in MODEL_PATHS
    }
    print(f"Successfully loaded {len(models)} models.")
except Exception as e:
    print(f"FATAL: Error loading models: {e}")
    # If models fail to load, the app cannot function.
    models = {}


def _calculate_score_from_text(text_to_embed: str, goal: str) -> int:
    """
    Computes embeddings for the given text and goal, calculates their
    cosine similarity, and returns a score from 0 to 100.
    """
    if not models:
        raise RuntimeError("Models are not loaded, cannot compute score.")

    scores = []
    for model_name, model in models.items():
        vec_text = model.encode(text_to_embed, convert_to_tensor=True)
        vec_goal = model.encode(goal, convert_to_tensor=True)
        cos_sim = util.cos_sim(vec_text, vec_goal).item()
        pct_score = max(0, min(100, int((cos_sim + 1) * 50)))
        scores.append(pct_score)

    if not scores:
        return 0
    
    return int(round(sum(scores) / len(scores)))


def compute_score(video_url: str, goal: str) -> int:
    """
    Fetches video metadata (title and description) and calculates a
    relevance score based on the provided goal.
    """
    title, desc = fetch_metadata(video_url)
    text_to_embed = f"{title}\n\n{desc}"
    final_score = _calculate_score_from_text(text_to_embed, goal)
    print(f"URL: {video_url}, Goal: '{goal}', Final Score: {final_score}")
    return final_score


def compute_score_from_title(video_url: str, goal: str) -> int:
    """
    Fetches video metadata (title only) and calculates a relevance score
    based on the provided goal.
    """
    title, _ = fetch_metadata(video_url)
    final_score = _calculate_score_from_text(title, goal)
    print(f"URL: {video_url}, Goal: '{goal}', Title-Only Score: {final_score}")
    return final_score


