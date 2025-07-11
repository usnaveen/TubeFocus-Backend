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


def compute_score(video_url: str, goal: str) -> int:
    """
    Fetches video metadata, computes embeddings using the local 5-model ensemble,
    calculates cosine-similarities, and averages the results for a final score.
    """
    if not models:
        raise RuntimeError("Models are not loaded, cannot compute score.")

    # A) Fetch metadata from YouTube
    title, desc = fetch_metadata(video_url)
    text_to_embed = f"{title}\n\n{desc}"

    # B) Compute one score per model
    scores = []
    for model_name, model in models.items():
        # The sentence_transformers library handles tokenization and pooling internally.
        vec_text = model.encode(text_to_embed, convert_to_tensor=True)
        vec_goal = model.encode(goal, convert_to_tensor=True)

        # Calculate cosine similarity
        cos_sim = util.cos_sim(vec_text, vec_goal).item()

        # Map the similarity score from a range of [-1, 1] to [0, 100]
        pct_score = int((cos_sim + 1) * 50)
        pct_score = max(0, min(100, pct_score)) # Ensure score is within 0-100
        scores.append(pct_score)

    # C) The final score is the average of all model scores
    if not scores:
        return 0
        
    final_score = int(round(sum(scores) / len(scores)))
    print(f"URL: {video_url}, Goal: '{goal}', Final Score: {final_score}")
    return final_score

