# test_models.py
# This script tests the locally downloaded models to ensure they load and function correctly.

from sentence_transformers import SentenceTransformer, util
import os
import numpy as np

# --- List of local model paths to test ---
# This should match the paths in your updated score_model.py
MODEL_PATHS = [
    "models/sentence-transformers_all-MiniLM-L6-v2",
    "models/sentence-transformers_multi-qa-MiniLM-L6-cos-v1",
    "models/sentence-transformers_paraphrase-MiniLM-L3-v2",
    "models/sentence-transformers_all-mpnet-base-v2",
    "models/sentence-transformers_all-distilroberta-v1"
]

# --- Sample sentences for testing ---
sentences = [
    "The cat sits on the mat.",
    "A feline is resting on the rug."
]

print("--- Starting Local Model Test ---")
print(f"Found {len(MODEL_PATHS)} models to test.\n")

all_tests_passed = True

# --- Test each model ---
for path in MODEL_PATHS:
    print(f"--- Testing model: {os.path.basename(path)} ---")

    # 1. Check if the directory exists
    if not os.path.exists(path):
        print(f"  [FAIL] Directory not found at: {path}")
        all_tests_passed = False
        continue
    
    print("  [OK]   Directory found.")

    try:
        # 2. Load the model from the local directory
        model = SentenceTransformer(path)
        print("  [OK]   Model loaded successfully.")

        # 3. Perform a test embedding
        embeddings = model.encode(sentences, convert_to_tensor=True)
        print("  [OK]   Sentences embedded successfully.")

        # 4. Calculate cosine similarity
        cos_sim = util.cos_sim(embeddings[0], embeddings[1])
        print(f"  [INFO] Similarity score: {cos_sim.item():.4f}")
        
        # A simple check to ensure the output is a valid number
        if isinstance(cos_sim.item(), float):
             print("  [OK]   Similarity calculation is valid.\n")
        else:
            raise TypeError("Similarity score is not a valid float.")

    except Exception as e:
        print(f"  [FAIL] An error occurred during the test: {e}\n")
        all_tests_passed = False

# --- Final Summary ---
print("--- Test Summary ---")
if all_tests_passed:
    print("✅ All models were loaded and tested successfully!")
else:
    print("❌ Some models failed the test. Please check the logs above.")


