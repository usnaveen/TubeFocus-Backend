from sentence_transformers import CrossEncoder
import os
import shutil

MODEL_NAME = 'cross-encoder/ms-marco-MiniLM-L6-v2'
TARGET_DIR = 'models/sentence-transformers_cross-encoder-ms-marco-MiniLM-L6-v2'

# Download to a temp directory using cache_dir
TEMP_DIR = 'models/temp_cross_encoder_download'

# Remove temp dir if it exists
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)

print(f"Downloading {MODEL_NAME} to {TEMP_DIR} ...")
model = CrossEncoder(MODEL_NAME, cache_dir=TEMP_DIR)

# Find the actual model directory inside TEMP_DIR
# It should contain config.json, pytorch_model.bin, etc.
for root, dirs, files in os.walk(TEMP_DIR):
    if 'config.json' in files and 'pytorch_model.bin' in files:
        model_dir = root
        break
else:
    raise RuntimeError('Could not find downloaded model files in temp directory.')

# Remove target dir if it exists
if os.path.exists(TARGET_DIR):
    shutil.rmtree(TARGET_DIR)

# Copy the model files to the target directory
shutil.copytree(model_dir, TARGET_DIR)
print(f"Model files copied to {TARGET_DIR}")

# Clean up temp dir
shutil.rmtree(TEMP_DIR)
print("Temporary files cleaned up.") 