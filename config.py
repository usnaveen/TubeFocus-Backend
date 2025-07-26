import json
import os

DEFAULT_WEIGHTS = {
    "description": 0.25,
    "title": 0.25,
    "tags": 0.25,
    "category": 0.25
}

WEIGHTS_FILE = "weights.json"

def load_weights():
    if os.path.exists(WEIGHTS_FILE):
        with open(WEIGHTS_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_WEIGHTS.copy()

def save_weights(weights):
    with open(WEIGHTS_FILE, 'w') as f:
        json.dump(weights, f, indent=2) 