# manage_models.py
# A script to download, manage, and test sentence-transformer models locally.

from sentence_transformers import SentenceTransformer, util
import os

# --- Model Configuration ---
# We will compare three models:
# 1. A good, small baseline model.
# 2. A medium-sized model optimized for your specific task (Recommended).
# 3. A large, state-of-the-art model for top performance.
MODELS_TO_MANAGE = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/msmarco-distilbert-base-tas-b", # Recommended for your use case
    "BAAI/bge-large-en-v1.5"
]

MODELS_DIR = "models"

# --- Test Cases ---
# A diverse set of examples to see how models perform.
TEST_CASES = {
    "High Similarity": [
        "A man is playing a guitar.",
        "Someone is performing music with a stringed instrument."
    ],
    "Low Similarity": [
        "The cat sits on the mat.",
        "The president is giving a speech about the economy."
    ],
    "Asymmetric Search (Your Use Case)": [
        "How to learn linear algebra?",
        "This video provides a comprehensive introduction to vector spaces, matrices, and eigenvalues, which are the fundamental concepts of linear algebra."
    ]
}

def download_model(model_name):
    """Checks if a model exists locally and downloads it if not."""
    save_path = os.path.join(MODELS_DIR, model_name.replace("/", "_"))

    if os.path.exists(save_path):
        print(f"  [INFO] Model '{model_name}' already exists locally. Skipping download.")
        return save_path

    print(f"  [ACTION] Downloading model '{model_name}'...")
    try:
        model = SentenceTransformer(model_name)
        model.save(save_path)
        print(f"  [SUCCESS] Model saved to {save_path}")
        return save_path
    except Exception as e:
        print(f"  [ERROR] Failed to download {model_name}. Error: {e}")
        return None

def test_model(model_path):
    """Loads a local model and tests it against all test cases."""
    if not model_path:
        return

    print(f"\n--- Testing Model: {os.path.basename(model_path)} ---")
    try:
        model = SentenceTransformer(model_path)
        for name, sentences in TEST_CASES.items():
            embeddings = model.encode(sentences, convert_to_tensor=True)
            cos_sim = util.cos_sim(embeddings[0], embeddings[1])
            score = cos_sim.item()
            print(f"  - Test Case '{name}':")
            print(f"    Similarity Score: {score:.4f}")
        print("--- Test Complete ---")
    except Exception as e:
        print(f"  [ERROR] Failed to test model. Error: {e}")


def main():
    """Main function to orchestrate downloading and testing."""
    print("===== Starting Model Management Script =====\n")
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)

    for model_name in MODELS_TO_MANAGE:
        print(f"\nProcessing model: {model_name}")
        local_path = download_model(model_name)
        
        # Only test if the model was successfully downloaded/found
        if local_path:
            test_model(local_path)

    print("\n===== Script Finished ======")

if __name__ == "__main__":
    main()


