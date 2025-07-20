import os
import re
from flask import Flask, request, jsonify
from youtube_scraper import fetch_metadata
from score_model import compute_score, compute_score_from_title

app = Flask(__name__)

# Health check
@app.route("/", methods=["GET"])
def home():
    return "YouTube Productivity Scorer is running!\n", 200

# Predict endpoint (uses title and description)
@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    video_url = data.get("video_url")
    goal      = data.get("goal")

    if not video_url or not goal:
        return jsonify({"error": "Missing video_url or goal"}), 400

    try:
        score = compute_score(video_url, goal)
        return jsonify({"score": score}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Predict title-only endpoint
@app.route("/predict_title", methods=["POST"])
def predict_title():
    data = request.get_json(force=True)
    video_url = data.get("video_url")
    goal      = data.get("goal")

    if not video_url or not goal:
        return jsonify({"error": "Missing video_url or goal"}), 400

    try:
        score = compute_score_from_title(video_url, goal)
        return jsonify({"score": score}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Use PORT env var for Cloud Run
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
