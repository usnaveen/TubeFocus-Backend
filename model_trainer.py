import numpy as np
from sklearn.neural_network import MLPRegressor
import joblib
import os
import hashlib
import json

MODEL_FILE = 'score_model.pkl'
MODEL_VERSION_FILE = 'model_versions.json'

# --- Model Versioning ---
def compute_model_hash(model):
    weights = model.coefs_ + model.intercepts_
    arr = np.concatenate([w.flatten() for w in weights])
    return hashlib.sha256(arr.tobytes()).hexdigest()

def save_model_version(version_hash):
    versions = {}
    if os.path.exists(MODEL_VERSION_FILE):
        with open(MODEL_VERSION_FILE, 'r') as f:
            versions = json.load(f)
    versions['latest'] = version_hash
    with open(MODEL_VERSION_FILE, 'w') as f:
        json.dump(versions, f, indent=2)

def get_latest_model_version():
    if not os.path.exists(MODEL_VERSION_FILE):
        return None
    with open(MODEL_VERSION_FILE, 'r') as f:
        versions = json.load(f)
    return versions.get('latest')

# Train the neural net on feedback data (X: features, y: user scores)
def train_and_save_model(X, y):
    mlp = MLPRegressor(hidden_layer_sizes=(8,), activation='relu', max_iter=500)
    mlp.fit(X, y)
    joblib.dump(mlp, MODEL_FILE)
    version_hash = compute_model_hash(mlp)
    save_model_version(version_hash)
    # Save versioned model file
    joblib.dump(mlp, f'score_model_{version_hash}.pkl')
    return mlp, version_hash

def load_model():
    if not os.path.exists(MODEL_FILE):
        return None
    return joblib.load(MODEL_FILE)

def load_model_version(version_hash):
    path = f'score_model_{version_hash}.pkl'
    if not os.path.exists(path):
        return None
    return joblib.load(path) 