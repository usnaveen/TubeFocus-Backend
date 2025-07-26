import logging
import os
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from youtube_api import fetch_video_details
from scoring_modules import score_description, score_title, score_tags, score_category
from data_manager import save_feedback, load_feedback
from model_trainer import train_and_save_model, load_model
import numpy as np

# --- Logging setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["chrome-extension://*"], methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-KEY"])

MIN_FEEDBACK = 5
API_KEY = os.environ.get('API_KEY', 'changeme')

# --- Security: API Key check ---
def require_api_key():
    key = request.headers.get('X-API-KEY')
    if not key or key != API_KEY:
        logger.warning('Unauthorized access attempt.')
        abort(401, description='Unauthorized: Invalid or missing API key.')

@app.before_request
def log_request_info():
    logger.info(f"{request.method} {request.path} - {request.remote_addr}")

@app.route('/health', methods=['GET'])
def health():
    return 'YouTube Relevance Scorer API is running!', 200

@app.route('/predict', methods=['POST'])
def predict():
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_id = data.get('video_id')
        goal = data.get('goal')
        parameters = data.get('parameters', ['title'])
        # Sanitize inputs
        if not isinstance(video_id, str) or not 5 < len(video_id) < 20:
            logger.warning('Invalid video_id in /predict')
            return jsonify({'error': 'Invalid video_id'}), 400
        if not isinstance(goal, str) or not 2 < len(goal) < 200:
            logger.warning('Invalid goal in /predict')
            return jsonify({'error': 'Invalid goal'}), 400
        if not isinstance(parameters, list) or not all(isinstance(p, str) for p in parameters):
            logger.warning('Invalid parameters in /predict')
            return jsonify({'error': 'Invalid parameters'}), 400
        details = fetch_video_details(video_id)
        if not details:
            # If YouTube API key is not configured, return a mock response for testing
            if not os.environ.get('YOUTUBE_API_KEY'):
                logger.warning(f'YouTube API key not configured, using mock data for {video_id}')
                details = {
                    'title': f'Test Video {video_id}',
                    'description': 'This is a test video description for development purposes.',
                    'tags': ['test', 'video', 'development'],
                    'category': 'Education'
                }
            else:
                logger.warning(f'Could not fetch video details for {video_id}')
                return jsonify({'error': 'Could not fetch video details'}), 400
        # Always compute ALL scores for caching
        title_score = score_title(goal, details['title'])
        desc_score = score_description(goal, details['title'], details['description'])
        tags_score = score_tags(goal, details['tags'])
        category_score = score_category(goal, details['category'])
        
        # Store all individual scores
        scores = {
            'title_score': title_score,
            'description_score': desc_score,
            'tags_score': tags_score,
            'category_score': category_score
        }
        
        # Calculate weighted average based on selected parameters
        selected_scores = []
        for param in parameters:
            if param == 'title':
                selected_scores.append(title_score)
            elif param == 'description':
                selected_scores.append(desc_score)
            elif param == 'tags':
                selected_scores.append(tags_score)
            elif param == 'category':
                selected_scores.append(category_score)
        
        # Calculate final score as average of selected parameters
        if len(selected_scores) == 1:
            final_score = selected_scores[0]
        else:
            final_score = sum(selected_scores) / len(selected_scores)
        
        scores['score'] = final_score
        # Add category name to response
        scores['category_name'] = details.get('category', 'Unknown')
        logger.info(f"/predict {video_id} {parameters} -> {final_score:.3f}")
        return jsonify(scores)
    except Exception as e:
        logger.error(f"/predict error: {e}", exc_info=True)
        return jsonify({'error': f'Internal server error: {e}'}), 500

@app.route('/feedback', methods=['POST'])
def feedback():
    require_api_key()
    try:
        data = request.get_json(force=True)
        # Sanitize inputs
        for k in ['desc_score', 'title_score', 'tags_score', 'category_score', 'user_score']:
            if k not in data or not isinstance(data[k], (int, float)):
                logger.warning(f'Missing or invalid {k} in /feedback')
                return jsonify({'error': f'Invalid or missing {k}'}), 400
        desc_score = float(data['desc_score'])
        title_score = float(data['title_score'])
        tags_score = float(data['tags_score'])
        category_score = float(data['category_score'])
        user_score = float(data['user_score'])
        save_feedback(desc_score, title_score, tags_score, category_score, user_score)
        feedback_data = load_feedback()
        retrained = False
        if len(feedback_data) >= MIN_FEEDBACK:
            X = np.array([[float(row['desc_score']), float(row['title_score']), float(row['tags_score']), float(row['category_score'])] for row in feedback_data])
            y = np.array([float(row['user_score']) for row in feedback_data])
            train_and_save_model(X, y)
            retrained = True
            logger.info('Model retrained after feedback.')
        logger.info('Feedback saved.')
        return jsonify({'status': 'Feedback saved', 'retrained': retrained})
    except Exception as e:
        logger.error(f"/feedback error: {e}", exc_info=True)
        return jsonify({'error': f'Internal server error: {e}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True) 