from sentence_transformers import CrossEncoder

print("Downloading cross-encoder/ms-marco-MiniLM-L6-v2 to Hugging Face default cache...")
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')
print("Download complete. Model is now in the Hugging Face cache directory.") 