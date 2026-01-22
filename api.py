import logging
import os

from flask import Flask, request, jsonify, abort
from flask_cors import CORS

# Import centralized configuration
from config import Config

from youtube_client import get_video_details
from scoring_modules import score_description, score_title, score_tags, score_category
from data_manager import save_feedback, load_feedback
from simple_scoring import compute_simple_score, compute_simple_score_from_title, compute_simple_score_title_and_clean_desc
from transcript_service import get_transcript, get_transcript_excerpt
from auditor_agent import get_auditor_agent
from coach_agent import get_coach_agent
from librarian_agent import get_librarian_agent
import numpy as np

# --- Custom Error Codes and Messages ---
class APIErrorCodes:
    # Video-related errors (1000-1099)
    VIDEO_NOT_FOUND = 1001
    VIDEO_PRIVATE = 1002
    VIDEO_DELETED = 1003
    INVALID_VIDEO_ID = 1004
    INVALID_VIDEO_URL = 1005
    
    # Data availability errors (1100-1199)
    MISSING_TITLE = 1101
    MISSING_DESCRIPTION = 1102
    MISSING_TAGS = 1103
    MISSING_CATEGORY = 1104
    INSUFFICIENT_DATA = 1105
    
    # API configuration errors (1200-1299)
    YOUTUBE_API_KEY_MISSING = 1201
    YOUTUBE_API_QUOTA_EXCEEDED = 1202
    YOUTUBE_API_DISABLED = 1203
    YOUTUBE_API_INVALID_KEY = 1204
    
    # Scoring errors (1300-1399)
    SCORING_MODELS_NOT_LOADED = 1301
    SCORING_FAILED = 1302
    INVALID_PARAMETERS = 1303
    
    # Request validation errors (1400-1499)
    INVALID_GOAL = 1401
    INVALID_API_KEY = 1402
    MISSING_REQUIRED_FIELDS = 1403
    
    # System errors (1500-1599)
    INTERNAL_ERROR = 1501
    SERVICE_UNAVAILABLE = 1502

class APIError(Exception):
    def __init__(self, error_code, message, http_status=400, details=None):
        self.error_code = error_code
        self.message = message
        self.http_status = http_status
        self.details = details or {}

def create_error_response(error_code, message, http_status=400, details=None):
    """Create standardized error response"""
    return jsonify({
        'error': True,
        'error_code': error_code,
        'message': message,
        'details': details or {},
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }), http_status

def handle_missing_data(details, required_parameters):
    """Check for missing data and return appropriate error codes"""
    missing_data = []
    available_parameters = []
    
    if 'title' in required_parameters:
        if not details.get('title'):
            missing_data.append('title')
        else:
            available_parameters.append('title')
    
    if 'description' in required_parameters:
        if not details.get('description'):
            missing_data.append('description')
        else:
            available_parameters.append('description')
    
    if 'tags' in required_parameters:
        if not details.get('tags') or len(details.get('tags', [])) == 0:
            missing_data.append('tags')
        else:
            available_parameters.append('tags')
    
    if 'category' in required_parameters:
        if not details.get('category'):
            missing_data.append('category')
        else:
            available_parameters.append('category')
    
    return missing_data, available_parameters

# --- Logging setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "X-API-KEY"])

# --- Security: API Key check ---
def require_api_key():
    key = request.headers.get('X-API-KEY')
    if not key or key != Config.API_KEY:
        logger.warning('Unauthorized access attempt.')
        # Raise a structured API error so clients always receive JSON
        raise APIError(APIErrorCodes.INVALID_API_KEY,
                       'Unauthorized: Invalid or missing API key.',
                       http_status=401)

@app.before_request
def log_request_info():
    logger.info(f"{request.method} {request.path} - {request.remote_addr}")

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint with system status"""
    try:
        return jsonify({
            'status': 'healthy',
            'service': 'YouTube Relevance Scorer API (Gemini Powered)',
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'system_info': {
                'youtube_api_key': "configured" if Config.YOUTUBE_API_KEY else "missing",
                'google_api_key': "configured" if Config.GOOGLE_API_KEY else "missing",
                'environment': Config.ENVIRONMENT,
                'python_version': __import__('sys').version
            }
        })
    except Exception as e:
        return create_error_response(
            APIErrorCodes.SERVICE_UNAVAILABLE,
            "Health check failed",
            503,
            {'error_details': str(e)}
        )

@app.route('/score/detailed', methods=['POST'])
def score_detailed():
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_id = data.get('video_id')
        goal = data.get('goal')
        parameters = data.get('parameters', ['title'])
        
        # Validate required fields
        if not video_id:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "video_id is required",
                400,
                {'missing_field': 'video_id'}
            )
        
        if not goal:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "goal is required",
                400,
                {'missing_field': 'goal'}
            )
        
        # Sanitize inputs
        if not isinstance(video_id, str) or not 5 < len(video_id) < 20:
            return create_error_response(
                APIErrorCodes.INVALID_VIDEO_ID,
                "Invalid video_id format",
                400,
                {'video_id': video_id, 'expected_format': '11-character YouTube video ID'}
            )
        
        if not isinstance(goal, str) or not 2 < len(goal) < 200:
            return create_error_response(
                APIErrorCodes.INVALID_GOAL,
                "Invalid goal format",
                400,
                {'goal': goal, 'expected_format': '2-200 characters'}
            )
        
        if not isinstance(parameters, list) or not all(isinstance(p, str) for p in parameters):
            return create_error_response(
                APIErrorCodes.INVALID_PARAMETERS,
                "Invalid parameters format",
                400,
                {'parameters': parameters, 'expected_format': 'List of strings'}
            )
        
        # Validate parameter values
        valid_parameters = ['title', 'description', 'tags', 'category']
        invalid_params = [p for p in parameters if p not in valid_parameters]
        if invalid_params:
            return create_error_response(
                APIErrorCodes.INVALID_PARAMETERS,
                "Invalid parameter values",
                400,
                {'invalid_parameters': invalid_params, 'valid_parameters': valid_parameters}
            )
        
        # Fetch video details
        details = get_video_details(video_id)
        if not details:
            # Check if it's a YouTube API issue
            if not Config.YOUTUBE_API_KEY:
                return create_error_response(
                    APIErrorCodes.YOUTUBE_API_KEY_MISSING,
                    "YouTube API key not configured",
                    503,
                    {'solution': 'Set YOUTUBE_API_KEY environment variable'}
                )
            else:
                return create_error_response(
                    APIErrorCodes.VIDEO_NOT_FOUND,
                    "Video not found or inaccessible",
                    404,
                    {'video_id': video_id, 'possible_reasons': ['Video is private', 'Video is deleted', 'Invalid video ID']}
                )
        
        # Check for missing data based on requested parameters
        missing_data, available_parameters = handle_missing_data(details, parameters)
        
        if missing_data:
            logger.warning(f"Missing data for video {video_id}: {missing_data}")
            # Continue with available parameters, but log the issue
        
        # Calculate scores for available parameters
        scores = {}
        selected_scores = []
        
        # Title scoring
        if 'title' in parameters:
            if details.get('title'):
                title_score = score_title(goal, details['title'])
                scores['title_score'] = title_score
                selected_scores.append(title_score)
            else:
                scores['title_score'] = 0.0
                logger.warning(f"Title missing for video {video_id}, setting score to 0")
        
        # Description scoring
        if 'description' in parameters:
            if details.get('description'):
                desc_score = score_description(goal, details.get('title', ''), details['description'])
                scores['description_score'] = desc_score
                selected_scores.append(desc_score)
            else:
                scores['description_score'] = 0.0
                logger.warning(f"Description missing for video {video_id}, setting score to 0")
        
        # Tags scoring
        if 'tags' in parameters:
            if details.get('tags') and len(details['tags']) > 0:
                tags_score = score_tags(goal, details['tags'])
                scores['tags_score'] = tags_score
                selected_scores.append(tags_score)
            else:
                scores['tags_score'] = 0.0
                logger.warning(f"Tags missing for video {video_id}, setting score to 0")
        
        # Category scoring
        if 'category' in parameters:
            if details.get('category'):
                category_score = score_category(goal, details['category'])
                scores['category_score'] = category_score
                selected_scores.append(category_score)
            else:
                scores['category_score'] = 0.0
                logger.warning(f"Category missing for video {video_id}, setting score to 0")
        
        # Calculate final score based on available parameters
        if len(selected_scores) == 0:
            return create_error_response(
                APIErrorCodes.INSUFFICIENT_DATA,
                "No scoring data available for requested parameters",
                400,
                {'requested_parameters': parameters, 'missing_data': missing_data, 'available_data': available_parameters}
            )
        
        # Calculate final score as average of available parameter scores
        if len(selected_scores) == 1:
            final_score = selected_scores[0]
        else:
            final_score = sum(selected_scores) / len(selected_scores)
        
        scores['score'] = final_score
        scores['category_name'] = details.get('category', 'Unknown')
        
        # Add metadata about the scoring process
        scores['scoring_metadata'] = {
            'parameters_requested': parameters,
            'parameters_available': available_parameters,
            'parameters_missing': missing_data,
            'score_calculation_method': 'average_of_available_parameters',
            'total_parameters_used': len(selected_scores)
        }
        
        logger.info(f"/score/detailed {video_id} {parameters} -> {final_score:.3f} (available: {available_parameters}, missing: {missing_data})")
        return jsonify(scores)
        
    except Exception as e:
        logger.error(f"/score/detailed error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Internal server error during scoring",
            500,
            {'error_details': str(e)}
        )

@app.route('/score/simple', methods=['POST'])
def score_simple():
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_url = data.get('video_url')
        goal = data.get('goal')
        mode = data.get('mode', 'title_and_description')  # Default to "title_and_description"
        transcript = data.get('transcript', '')

        # Validate required fields
        if not video_url:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "video_url is required",
                400,
                {'missing_field': 'video_url'}
            )
        
        if not goal:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "goal is required",
                400,
                {'missing_field': 'goal'}
            )

        # Sanitize inputs
        if not isinstance(video_url, str) or not video_url:
            return create_error_response(
                APIErrorCodes.INVALID_VIDEO_URL,
                "Invalid video_url format",
                400,
                {'video_url': video_url, 'expected_format': 'Valid YouTube URL'}
            )
        
        if not isinstance(goal, str) or not 2 < len(goal) < 200:
            return create_error_response(
                APIErrorCodes.INVALID_GOAL,
                "Invalid goal format",
                400,
                {'goal': goal, 'expected_format': '2-200 characters'}
            )
        
        if mode not in ['title_only', 'title_and_description', 'title_and_clean_desc']:
            return create_error_response(
                APIErrorCodes.INVALID_PARAMETERS,
                "Invalid mode value",
                400,
                {'mode': mode, 'valid_modes': ['title_only', 'title_and_description', 'title_and_clean_desc']}
            )

        # Check YouTube API key availability
        if not Config.YOUTUBE_API_KEY:
            return create_error_response(
                APIErrorCodes.YOUTUBE_API_KEY_MISSING,
                "YouTube API key not configured",
                503,
                {'solution': 'Set YOUTUBE_API_KEY environment variable'}
            )

        # Compute score using simplified approach
        try:
            if mode == "title_only":
                # These alias functions need update too if used, but for now specific on main function
                score = compute_simple_score_from_title(video_url, goal)
                debug_info = {}
            elif mode == "title_and_clean_desc":
                score = compute_simple_score_title_and_clean_desc(video_url, goal)
                debug_info = {}
            else:
                score, reasoning, debug_info = compute_simple_score(video_url, goal, transcript=transcript)
            
            logger.info(f"/score/simple {video_url} {mode} -> {score}")
            return jsonify({
                "score": score, 
                "mode": mode,
                "video_url": video_url,
                "goal": goal,
                "debug_details": debug_info
            }), 200
            
        except ValueError as ve:
            # Check if we have attached debug info
            debug_details = getattr(ve, 'debug_info', {})
            
            # Handle video not found, private, deleted, etc.
            if "Video not found" in str(ve):
                return create_error_response(
                    APIErrorCodes.VIDEO_NOT_FOUND,
                    "Video not found or inaccessible",
                    404,
                    {'video_url': video_url, 'possible_reasons': ['Video is private', 'Video is deleted', 'Invalid URL'], 'debug_details': debug_details}
                )
            else:
                return create_error_response(
                    APIErrorCodes.INVALID_VIDEO_URL,
                    "Invalid video URL format",
                    400,
                    {'video_url': video_url, 'error': str(ve), 'debug_details': debug_details}
                )
                
        except RuntimeError as re:
            if "Simple scoring models are not loaded" in str(re):
                return create_error_response(
                    APIErrorCodes.SCORING_MODELS_NOT_LOADED,
                    "Scoring models not available",
                    503,
                    {'solution': 'Check if models are properly loaded'}
                )
            else:
                raise re
        
    except Exception as e:
        logger.error(f"/score/simple error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Internal server error during simple scoring",
            500,
            {'error_details': str(e)}
        )

@app.route('/feedback', methods=['POST'])
def feedback():
    require_api_key()
    try:
        data = request.get_json(force=True)
        
        # Validate required fields
        required_fields = ['desc_score', 'title_score', 'tags_score', 'category_score', 'user_score']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "Missing required feedback fields",
                400,
                {'missing_fields': missing_fields, 'required_fields': required_fields}
            )
        
        # Validate field types and values
        feedback_scores = {}
        for field in required_fields:
            value = data[field]
            if not isinstance(value, (int, float)):
                return create_error_response(
                    APIErrorCodes.INVALID_PARAMETERS,
                    f"Invalid {field} type",
                    400,
                    {'field': field, 'value': value, 'expected_type': 'number'}
                )
            
            # Validate score range (0-1 for API scores, 0-100 for user score)
            if field == 'user_score':
                if not (0 <= value <= 100):
                    return create_error_response(
                        APIErrorCodes.INVALID_PARAMETERS,
                        f"Invalid {field} value",
                        400,
                        {'field': field, 'value': value, 'expected_range': '0-100'}
                    )
            else:
                if not (0 <= value <= 1):
                    return create_error_response(
                        APIErrorCodes.INVALID_PARAMETERS,
                        f"Invalid {field} value",
                        400,
                        {'field': field, 'value': value, 'expected_range': '0-1'}
                    )
            
            feedback_scores[field] = float(value)
        
        # Save feedback
        save_feedback(
            feedback_scores['desc_score'],
            feedback_scores['title_score'], 
            feedback_scores['tags_score'],
            feedback_scores['category_score'],
            feedback_scores['user_score']
        )
        
        # Check if retraining is needed
        # feedback_data = load_feedback()
        # retrained = False
        # Retraining disabled for API-only mode
        retrained = False
        feedback_data = []  # Placeholder since retraining is disabled
        
        logger.info('Feedback saved successfully.')
        return jsonify({
            'status': 'Feedback saved', 
            'retrained': retrained,
            'total_feedback_count': len(feedback_data)
        })
        
    except Exception as e:
        logger.error(f"/feedback error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Internal server error during feedback processing",
            500,
            {'error_details': str(e)}
        )

@app.route('/transcript/<video_id>', methods=['GET'])
def transcript_endpoint(video_id):
    """
    Transcript extraction endpoint for Auditor Agent.
    GET /transcript/<video_id>
    """
    require_api_key()
    try:
        logger.info(f"Fetching transcript for video: {video_id}")
        
        # Get transcript using the transcript service
        transcript_data = get_transcript(video_id)
        
        if transcript_data.get('error'):
            return jsonify({
                'success': False,
                'error': transcript_data['error'],
                'transcript': None,
                'segments': []
            }), 404
        
        return jsonify({
            'success': True,
            'transcript': transcript_data['transcript'],
            'segments': transcript_data['segments'],
            'language': transcript_data.get('language'),
            'is_generated': transcript_data.get('is_generated'),
            'video_id': video_id
        }), 200
        
    except Exception as e:
        logger.error(f"/transcript error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to fetch transcript",
            500,
            {'error_details': str(e), 'video_id': video_id}
        )

@app.route('/audit', methods=['POST'])
def audit_video():
    """
    Auditor Agent endpoint - Content verification and clickbait detection.
    POST /audit
    Body: {
        "video_id": "...",
        "title": "...",
        "description": "...",
        "goal": "...",
        "transcript": "..." (optional)
    }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_id = data.get('video_id')
        title = data.get('title')
        description = data.get('description', '')
        goal = data.get('goal')
        transcript = data.get('transcript')  # Optional
        
        # Validate required fields
        if not video_id:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "video_id is required",
                400,
                {'missing_field': 'video_id'}
            )
        
        if not title:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "title is required",
                400,
                {'missing_field': 'title'}
            )
        
        if not goal:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "goal is required",
                400,
                {'missing_field': 'goal'}
            )
        
        # Get Auditor Agent instance
        auditor = get_auditor_agent()
        
        # Perform autonomous analysis
        logger.info(f"Auditor analyzing video: {video_id} for goal: {goal}")
        analysis = auditor.analyze_content(
            video_id=video_id,
            title=title,
            description=description,
            goal=goal,
            transcript=transcript
        )
        
        # Return analysis results
        return jsonify({
            'success': True,
            'video_id': video_id,
            'analysis': analysis,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"/audit error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Auditor analysis failed",
            500,
            {'error_details': str(e)}
        )

@app.route('/coach/analyze', methods=['POST'])
def coach_analyze():
    """
    Coach Agent endpoint - Session analysis and behavior intervention.
    POST /coach/analyze
    Body: {
        "session_id": "...",
        "goal": "...",
        "session_data": [
            {"video_id": "...", "title": "...", "score": 75, "timestamp": "..."},
            ...
        ]
    }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        session_id = data.get('session_id')
        goal = data.get('goal')
        session_data = data.get('session_data', [])
        
        # Validate required fields
        if not session_id:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "session_id is required",
                400,
                {'missing_field': 'session_id'}
            )
        
        if not goal:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "goal is required",
                400,
                {'missing_field': 'goal'}
            )
        
        if not isinstance(session_data, list):
            return create_error_response(
                APIErrorCodes.INVALID_PARAMETERS,
                "session_data must be an array",
                400,
                {'provided_type': type(session_data).__name__}
            )
        
        # Get Coach Agent instance
        coach = get_coach_agent()
        
        # Perform autonomous analysis
        logger.info(f"Coach analyzing session: {session_id} with {len(session_data)} videos")
        analysis = coach.analyze_session(
            session_id=session_id,
            session_data=session_data,
            goal=goal
        )
        
        # Return analysis results
        return jsonify({
            'success': True,
            'session_id': session_id,
            'analysis': analysis,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"/coach/analyze error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Coach analysis failed",
            500,
            {'error_details': str(e)}
        )

@app.route('/coach/stats/<session_id>', methods=['GET'])
def coach_stats(session_id):
    """
    Get session statistics from Coach Agent.
    GET /coach/stats/<session_id>
    """
    require_api_key()
    try:
        coach = get_coach_agent()
        stats = coach.get_session_stats(session_id)
        
        if not stats:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'stats': stats
        }), 200
        
    except Exception as e:
        logger.error(f"/coach/stats error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to retrieve session stats",
            500,
            {'error_details': str(e)}
        )

@app.route('/librarian/index', methods=['POST'])
def librarian_index():
    """
    Librarian Agent endpoint - Index a video for search.
    POST /librarian/index
    Body: {
        "video_id": "...",
        "title": "...",
        "transcript": "...",
        "goal": "...",
        "score": 75,
        "metadata": {} (optional)
    }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_id = data.get('video_id')
        title = data.get('title')
        transcript = data.get('transcript')
        goal = data.get('goal')
        score = data.get('score')
        metadata = data.get('metadata', {})
        
        # Validate required fields
        if not video_id:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "video_id is required",
                400,
                {'missing_field': 'video_id'}
            )
        
        if not title:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "title is required",
                400,
                {'missing_field': 'title'}
            )
        
        if not transcript:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "transcript is required",
                400,
                {'missing_field': 'transcript'}
            )
        
        if not goal:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "goal is required",
                400,
                {'missing_field': 'goal'}
            )
        
        if score is None:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "score is required",
                400,
                {'missing_field': 'score'}
            )
        
        # Get Librarian Agent instance
        librarian = get_librarian_agent()
        
        # Index the video
        logger.info(f"Librarian indexing video: {video_id}")
        success = librarian.index_video(
            video_id=video_id,
            title=title,
            transcript=transcript,
            goal=goal,
            score=score,
            metadata=metadata
        )
        
        if success:
            stats = librarian.get_stats()
            return jsonify({
                'success': True,
                'video_id': video_id,
                'message': 'Video indexed successfully',
                'stats': stats
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to index video'
            }), 500
        
    except Exception as e:
        logger.error(f"/librarian/index error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Librarian indexing failed",
            500,
            {'error_details': str(e)}
        )

@app.route('/librarian/search', methods=['POST'])
def librarian_search():
    """
    Librarian Agent endpoint - Semantic search over history.
    POST /librarian/search
    Body: {
        "query": "...",
        "n_results": 5 (optional),
        "goal_filter": "..." (optional)
    }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        query = data.get('query')
        n_results = data.get('n_results', 5)
        goal_filter = data.get('goal_filter')
        
        # Validate required fields
        if not query:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "query is required",
                400,
                {'missing_field': 'query'}
            )
        
        # Get Librarian Agent instance
        librarian = get_librarian_agent()
        
        # Perform search
        logger.info(f"Librarian searching for: '{query}'")
        results = librarian.search_history(
            query=query,
            n_results=n_results,
            goal_filter=goal_filter
        )
        
        return jsonify({
            'success': True,
            'search_results': results
        }), 200
        
    except Exception as e:
        logger.error(f"/librarian/search error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Librarian search failed",
            500,
            {'error_details': str(e)}
        )

@app.route('/librarian/video/<video_id>', methods=['GET'])
def librarian_get_video(video_id):
    """
    Get full indexed video by ID.
    GET /librarian/video/<video_id>
    """
    require_api_key()
    try:
        librarian = get_librarian_agent()
        video = librarian.get_video_by_id(video_id)
        
        if video:
            return jsonify({
                'success': True,
                'video': video
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Video not found'
            }), 404
        
    except Exception as e:
        logger.error(f"/librarian/video error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to retrieve video",
            500,
            {'error_details': str(e)}
        )

@app.route('/librarian/stats', methods=['GET'])
def librarian_stats():
    """
    Get Librarian statistics.
    GET /librarian/stats
    """
    require_api_key()
    try:
        librarian = get_librarian_agent()
        stats = librarian.get_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
        
    except Exception as e:
        logger.error(f"/librarian/stats error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to retrieve stats",
            500,
            {'error_details': str(e)}
        )

# Global error handler for unhandled exceptions
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    logger.error(f"Unhandled exception: {error}", exc_info=True)
    return create_error_response(
        APIErrorCodes.INTERNAL_ERROR,
        "An unexpected error occurred",
        500,
        {'error_type': type(error).__name__, 'error_details': str(error)}
    )

# Handle structured API errors consistently as JSON
@app.errorhandler(APIError)
def handle_api_error(error):
    return create_error_response(error.error_code, error.message, error.http_status, error.details)

# 404 handler for undefined routes
@app.errorhandler(404)
def not_found(error):
    return create_error_response(
        APIErrorCodes.INTERNAL_ERROR,
        "Endpoint not found",
        404,
        {'requested_url': request.url, 'available_endpoints': ['/health', '/score/detailed', '/score/simple', '/feedback', '/transcript/<video_id>', '/audit', '/coach/analyze', '/coach/stats/<session_id>', '/librarian/index', '/librarian/search', '/librarian/video/<video_id>', '/librarian/stats']}
    )

# 405 handler for method not allowed
@app.errorhandler(405)
def method_not_allowed(error):
    return create_error_response(
        APIErrorCodes.INVALID_PARAMETERS,
        "Method not allowed",
        405,
        {'method': request.method, 'endpoint': request.path, 'allowed_methods': ['GET', 'POST']}
    )


if __name__ == '__main__':
    logger.info(f"Starting TubeFocus API server...")
    logger.info(f"Environment: {Config.ENVIRONMENT}")
    logger.info(f"Debug mode: {Config.DEBUG}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)