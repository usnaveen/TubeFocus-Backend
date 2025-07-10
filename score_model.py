# score_model.py

from transformers import AutoTokenizer, AutoModel
import torch
from youtube_scraper import fetch_metadata

# 1) List of models to ensemble
MODEL_NAMES = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
    "sentence-transformers/paraphrase-MiniLM-L3-v2"
]

# 2) Load tokenizers & models just once
tokenizers = {
    name: AutoTokenizer.from_pretrained(name)
    for name in MODEL_NAMES
}  # :contentReference[oaicite:3]{index=3}

models = {
    name: AutoModel.from_pretrained(name)
    for name in MODEL_NAMES
}  # :contentReference[oaicite:4]{index=4}

def embed(text: str, name: str) -> torch.Tensor:
    """
    Tokenize and mean-pool the last hidden state to get a sentence embedding.
    """
    tokenizer = tokenizers[name]
    model     = models[name]

    # Tokenize with truncation & padding
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=512
    )
    outputs = model(**inputs)
    last_hidden = outputs.last_hidden_state  # [1, seq_len, dim]

    # Create mask to ignore padding tokens
    mask = inputs["attention_mask"].unsqueeze(-1).expand(last_hidden.size()).float()
    # Mean-pool: sum over tokens ÷ token count (ignores pads) :contentReference[oaicite:5]{index=5}
    sum_vec = (last_hidden * mask).sum(1)
    sum_mask = mask.sum(1).clamp(min=1e-9)
    return sum_vec / sum_mask

def compute_score(video_url: str, goal: str) -> int:
    """
    Fetch title/description, compute embeddings, cosine-similarities, then average.
    """
    # A) Fetch metadata
    title, desc = fetch_metadata(video_url)
    text = f"{title}\n\n{desc}"

    # B) Compute one score per model
    scores = []
    for name in MODEL_NAMES:
        vec_text = embed(text, name)
        vec_goal = embed(goal, name)

        # Cosine similarity between two 1×D tensors :contentReference[oaicite:6]{index=6}
        cos_sim = torch.nn.functional.cosine_similarity(vec_text, vec_goal, dim=1).item()  # –1..+1

        # Map –1..+1 → 0..100
        pct = int((cos_sim + 1) * 50)
        pct = max(0, min(100, pct))
        scores.append(pct)

    # C) Final score is the average
    return int(round(sum(scores) / len(scores)))
