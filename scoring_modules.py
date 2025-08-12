import os
import re
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder, util
from transformers import pipeline

# --- Model paths (local) ---
EMBEDDING_MODEL_PATH = "sentence-transformers/all-MiniLM-L6-v2"
CROSS_ENCODER_PATH = "cross-encoder/ms-marco-MiniLM-L-6-v2"
ZERO_SHOT_MODEL_PATH = "facebook/bart-large-mnli"

# --- Load models from local paths ---
embedding_model = SentenceTransformer(EMBEDDING_MODEL_PATH)
cross_encoder = CrossEncoder(CROSS_ENCODER_PATH)
classifier = pipeline(
    "zero-shot-classification",
    model=ZERO_SHOT_MODEL_PATH,
    multi_label=True,
    hypothesis_template="This video is about {}"
)

# --- Helper: Goal Deconstruction ---
def deconstruct_goal(goal):
    sub_goals = re.split(r',| and | particularly ', goal)
    sub_goals.append(goal)
    return [g.strip() for g in sub_goals if g.strip()]

# --- 1. Description Scoring ---
def score_description(goal, title, description):
    """Score based on title+description using embeddings and cross-encoder."""
    if not (goal and (title or description)):
        return 0.0
    video_content = f"{title}. {description}" if description else title
    sub_goals = deconstruct_goal(goal)
    best_score = 0.0
    for g in sub_goals:
        # Embedding similarity
        goal_emb = embedding_model.encode(g, convert_to_tensor=True)
        content_emb = embedding_model.encode(video_content, convert_to_tensor=True)
        emb_sim = float(util.cos_sim(goal_emb, content_emb).item())
        # Cross-encoder
        ce_score = float(cross_encoder.predict([(g, video_content)])[0])
        if ce_score > 1.0:
            ce_score = 1.0 / (1.0 + np.exp(-ce_score))
        # Title-goal similarity
        title_emb = embedding_model.encode(title, convert_to_tensor=True)
        title_sim = float(util.cos_sim(goal_emb, title_emb).item())
        # Keyword overlap
        goal_words = set(g.lower().split())
        content_words = set(video_content.lower().split())
        keyword_overlap = len(goal_words & content_words) / len(goal_words) if goal_words else 0
        # Weighted sum
        score = (
            0.35 * emb_sim +
            0.30 * ce_score +
            0.25 * title_sim +
            0.10 * keyword_overlap
        )
        best_score = max(best_score, score)
    # Normalize to 0-1
    return max(0.0, min(1.0, best_score))

# --- 2. Title Scoring ---
def score_title(goal, title):
    """Score based on title only using embeddings."""
    if not (goal and title):
        return 0.0
    sub_goals = deconstruct_goal(goal)
    best_score = 0.0
    for g in sub_goals:
        goal_emb = embedding_model.encode(g, convert_to_tensor=True)
        title_emb = embedding_model.encode(title, convert_to_tensor=True)
        sim = float(util.cos_sim(goal_emb, title_emb).item())
        best_score = max(best_score, sim)
    return max(0.0, min(1.0, best_score))

# --- 3. Tag Scoring ---
def score_tags(goal, tags_list, threshold=0.5, min_tags=1):
    """Score based on tags using zero-shot classification."""
    if not tags_list:
        return 0.0
    zs = classifier(goal, candidate_labels=tags_list)
    labels, scores = zs["labels"], zs["scores"]
    relevant = [(lbl, sc) for lbl, sc in zip(labels, scores) if sc >= threshold]
    n_total = len(tags_list)
    n_relevant = len(relevant)
    coverage = n_relevant / n_total
    if n_relevant >= min_tags:
        mean_conf = sum(sc for _, sc in relevant) / n_relevant
        composite = coverage * mean_conf
    else:
        mean_conf = 0.0
        composite = 0.0
    return max(0.0, min(1.0, composite))

# --- 4. Category Scoring ---
def score_category(goal, category_name):
    """Score based on category using zero-shot classification."""
    if not (goal and category_name):
        return 0.0
    out = classifier(goal, candidate_labels=[category_name])
    return max(0.0, min(1.0, float(out["scores"][0]))) 