import os
import re
from flask import Flask, request, jsonify
from youtube_scraper import fetch_metadata
from score_model import compute_score, compute_score_from_title

# Vertex AI Gemini imports
import os
from google.cloud import aiplatform
from google.cloud.aiplatform.gapic.schema import predict

app = Flask(__name__)

# --- Gemini 1.5 summary helper ---
def build_gemini_prompt(goal, videos):
    return f'''
<persona>
You are a witty and insightful AI assistant. You are a bit sarcastic but ultimately encouraging. Your goal is to summarize a user's video-watching session in a fun, engaging, and slightly snarky way, always relating it back to their stated goal.
</persona>

Here are some examples of how to perform the task:

<example>
<context>
  <user_goal>Learn Python for data science</user_goal>
  <videos>
    [
      {{"title": "Python for Beginners - Full Course"}},
      {{"title": "Data Structures and Algorithms in Python"}},
      {{"title": "10 Hours of Relaxing Rain Sounds"}},
      {{"title": "NumPy Tutorial: The Absolute Basics for Beginners"}}
    ]
  </videos>
</context>
<summary>
Looks like you were on a solid Python marathon... until you got mesmerized by rain for 10 hours. Classic focus drift! Still, you knocked out some foundational data science content. The path to becoming a data wizard is paved with good tutorials and the occasional "just resting my eyes" session. Keep it up!
</summary>
</example>

<example>
<context>
  <user_goal>Improve my public speaking skills</user_goal>
  <videos>
    [
      {{"title": "The surprising secret to speaking with confidence | Caroline Goyder | TEDxBrixton"}},
      {{"title": "How to Start a Speech"}},
      {{"title": "How to NOT Be Boring"}}
    ]
  </videos>
</context>
<summary>
Three videos on public speaking! You're clearly gearing up to deliver a speech that will be anything but boring. You've gone from theory to practical tips. Next step: practice in front of a mirror until your reflection gives you a standing ovation. You're on the right track!
</summary>
</example>

---

Now, perform the following task based on the examples above.

<task>
Analyze the user's goal and the list of watched videos. Generate a short, witty, and goal-aware summary of their session.
</task>

<rules>
- The summary must be concise (2-4 sentences).
- The tone should be sarcastic but encouraging, as shown in the persona.
- Directly reference the user's goal.
- If the videos are completely unrelated to the goal, gently poke fun at the distraction.
- Do not just list the videos. Synthesize the activity.
- The output should ONLY be the summary text, with no extra formatting or preamble.
</rules>

<context>
  <user_goal>{goal}</user_goal>
  <videos>
    {videos}
  </videos>
</context>
'''

def call_gemini_summary(prompt):
    # You must set GOOGLE_APPLICATION_CREDENTIALS in your environment for this to work
    # and have access to Vertex AI Gemini 1.5 Flash
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = "us-central1"
    model = "gemini-1.5-flash-001"
    aiplatform.init(project=project, location=location)
    response = aiplatform.TextGenerationModel.from_pretrained(model).predict(prompt, temperature=0.7, max_output_tokens=256)
    return response.text.strip()

# --- New /upload endpoint ---
@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json(force=True)
    goal = data.get("goal")
    session = data.get("session")
    if not goal or not session:
        return jsonify({"error": "Missing goal or session"}), 400
    # Prepare videos for prompt
    videos_json = str([{ 'title': v.get('title', '') } for v in session])
    prompt = build_gemini_prompt(goal, videos_json)
    try:
        summary = call_gemini_summary(prompt)
    except Exception as e:
        return jsonify({"error": f"Gemini call failed: {e}"}), 500
    return jsonify({"summary": summary})

# Health check
@app.route("/", methods=["GET"])
def home():
    return "YouTube Productivity Scorer is running!\n", 200

# Predict endpoint
@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    video_url = data.get("video_url")
    goal = data.get("goal")
    mode = data.get("mode", "title_and_description")  # Default to "title_and_description"

    if not video_url or not goal:
        return jsonify({"error": "Missing video_url or goal"}), 400

    try:
        if mode == "title_only":
            score = compute_score_from_title(video_url, goal)
        else:
            score = compute_score(video_url, goal)
        
        return jsonify({"score": score}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Use PORT env var for Cloud Run
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
