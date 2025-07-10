# download_models.py
# This script is designed to be robust against network errors.
# You can run it multiple times, and it will only download missing models.

from sentence_transformers import SentenceTransformer
import os

# --- List of 5 models for the ensemble ---
MODEL_NAMES = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
    "sentence-transformers/paraphrase-MiniLM-L3-v2",
    "sentence-transformers/all-mpnet-base-v2",
    "sentence-transformers/all-distilroberta-v1"
]

# --- Directory to save the models ---
MODELS_DIR = "models"
if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

# --- Download and save each model ---
for name in MODEL_NAMES:
    # Create a path-friendly name for the directory
    save_path = os.path.join(MODELS_DIR, name.replace("/", "_"))

    # --- FIX 1: Check if the model is already downloaded ---
    if os.path.exists(save_path):
        print(f"Model '{name}' already downloaded. Skipping.")
        continue

    try:
        print(f"Downloading {name}...")
        
        model = SentenceTransformer(name)
        
        print(f"Saving to {save_path}...")
        model.save(save_path)
        
        print(f"Finished downloading {name}.\n")

    # --- FIX 2: Handle potential network errors ---
    except Exception as e:
        print(f"---!!! FAILED to download {name}. Error: {e} !!!---\n")
        print("Continuing to the next model...")


print("Model download process finished. If any models failed, please run the script again.")
