import json
import os

DEFAULT_WEIGHTS = {
    "description": 0.25,
    "title": 0.25,
    "tags": 0.25,
    "category": 0.25
}

WEIGHTS_FILE = "weights.json"

# Redis Configuration
REDIS_HOST = "redis-12918.c212.ap-south-1-1.ec2.redns.redis-cloud.com"
REDIS_PORT = 12918
REDIS_DB = 0
REDIS_PASSWORD = "eps749EJLcCgzpJnkbfTxShVnQhjenpe"
REDIS_USERNAME = "default"
CACHE_TTL_SECONDS = 60 * 60 * 24 # 24 hours

def load_weights():
    if os.path.exists(WEIGHTS_FILE):
        with open(WEIGHTS_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_WEIGHTS.copy()

def save_weights(weights):
    with open(WEIGHTS_FILE, 'w') as f:
        json.dump(weights, f, indent=2)