import os
from sentence_transformers import SentenceTransformer, CrossEncoder
from transformers import AutoModelForSequenceClassification, AutoTokenizer

os.makedirs('models', exist_ok=True)

MODELS = {
    'sentence-transformers_all-MiniLM-L6-v2': 'sentence-transformers/all-MiniLM-L6-v2',
    'sentence-transformers_cross-encoder-ms-marco-MiniLM-L6-v2': 'cross-encoder/ms-marco-MiniLM-L6-v2',
    'facebook_bart-large-mnli': 'facebook/bart-large-mnli',
}

def download_sentence_transformer(model_name, local_dir):
    if not os.path.exists(local_dir):
        print(f"Downloading {model_name} to {local_dir}...")
        SentenceTransformer(model_name, cache_folder=local_dir)
    else:
        print(f"{local_dir} already exists, skipping.")

def download_cross_encoder(model_name, local_dir):
    if not os.path.exists(local_dir):
        print(f"Downloading {model_name} to {local_dir}...")
        CrossEncoder(model_name, cache_folder=local_dir)
    else:
        print(f"{local_dir} already exists, skipping.")

def download_bart_large_mnli(model_name, local_dir):
    if not os.path.exists(local_dir):
        print(f"Downloading {model_name} to {local_dir}...")
        AutoModelForSequenceClassification.from_pretrained(model_name, cache_dir=local_dir)
        AutoTokenizer.from_pretrained(model_name, cache_dir=local_dir)
    else:
        print(f"{local_dir} already exists, skipping.")

def main():
    download_sentence_transformer(MODELS['sentence-transformers_all-MiniLM-L6-v2'], 'models/sentence-transformers_all-MiniLM-L6-v2')
    download_cross_encoder(MODELS['sentence-transformers_cross-encoder-ms-marco-MiniLM-L6-v2'], 'models/sentence-transformers_cross-encoder-ms-marco-MiniLM-L6-v2')
    download_bart_large_mnli(MODELS['facebook_bart-large-mnli'], 'models/facebook_bart-large-mnli')

if __name__ == '__main__':
    main() 