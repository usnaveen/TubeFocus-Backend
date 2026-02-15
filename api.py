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
from navigator_agent import get_navigator_agent
from gatekeeper_agent import get_gatekeeper_agent
from intent_agent import get_intent_agent
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

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google import genai

# ... (imports)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "X-API-KEY"])

# --- Rate Limiter Setup ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[Config.RATELIMIT_DEFAULT],
    storage_uri=Config.RATELIMIT_STORAGE_URL
)

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
@limiter.exempt  # Exempt health check from rate limits
def health():
    """Health check endpoint with system status and dependency verification"""
    
    # Verify Dependencies
    dependencies = {
        'youtube_api': {'status': 'unknown', 'latency_ms': 0},
        'gemini_api': {'status': 'unknown', 'latency_ms': 0}
    }
    
    status = 'healthy'
    
    # Check 1: YouTube API (via Client)
    start_time = __import__('time').time()
    try:
        # Simple lightweight call to verify connectivity
        if Config.YOUTUBE_API_KEY:
             # Minimal call to check key validity (using requests directly or client)
             # We rely on Config validation usually, but here we can check connectivity if desired.
             # For now, just checking configuration as "healthy" implies configuration is present.
             dependencies['youtube_api']['status'] = 'configured'
        else:
             dependencies['youtube_api']['status'] = 'missing'
             status = 'degraded'
    except Exception as e:
        dependencies['youtube_api']['status'] = f'error: {str(e)}'
        status = 'degraded'
    dependencies['youtube_api']['latency_ms'] = int((__import__('time').time() - start_time) * 1000)

    # Check 2: Gemini API
    start_time = __import__('time').time()
    try:
        if Config.GOOGLE_API_KEY:
            client = genai.Client(api_key=Config.GOOGLE_API_KEY)
            # List models as a lightweight check
            list(client.models.list_models(page_size=1)) 
            dependencies['gemini_api']['status'] = 'connected'
        else:
            dependencies['gemini_api']['status'] = 'missing'
            status = 'degraded'
    except Exception as e:
        dependencies['gemini_api']['status'] = f'error: {str(e)}'
        status = 'unhealthy' # Critical dependency
    dependencies['gemini_api']['latency_ms'] = int((__import__('time').time() - start_time) * 1000)

    # Check 3: Firestore (via Librarian Agent connection check)
    start_time = __import__('time').time()
    try:
        from librarian_agent import get_librarian_agent
        agent = get_librarian_agent()
        if agent and agent.db:
            # Lightweight check: Access collection reference (doesn't make network call yet usually)
            # or try a minimal read. Let's trust initialization.
            dependencies['firestore'] = {'status': 'connected', 'latency_ms': 0}
        else:
            dependencies['firestore'] = {'status': 'disconnected', 'latency_ms': 0}
            status = 'degraded' # Librarian features unavailable
    except Exception as e:
        dependencies['firestore'] = {'status': f'error: {str(e)}', 'latency_ms': 0}
        status = 'degraded'
    dependencies['firestore']['latency_ms'] = int((__import__('time').time() - start_time) * 1000)

    try:
        return jsonify({
            'status': status,
            'service': 'TubeFocus API',
            'timestamp': __import__('datetime').datetime.now().isoformat(),
            'dependencies': dependencies,
            'system_info': {
                'environment': Config.ENVIRONMENT,
                'python_version': __import__('sys').version
            }
        }), 200 # Always return 200 to allow clients to see the status details
    except Exception as e:
        return create_error_response(
            APIErrorCodes.SERVICE_UNAVAILABLE,
            "Health check failed",
            200, # Return 200 even on error to see details
            {'error_details': str(e)}
        )



@app.route('/score', methods=['POST'])
def score_endpoint():
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_url = data.get('video_url')
        goal = data.get('goal')
        goal = data.get('goal')
        mode = data.get('mode', 'title_and_description')  # Default to "title_and_description"
        transcript = data.get('transcript', '')

        # Infer Intent (Cached/Lightweight)
        intent = get_intent_agent().infer_intent(goal)
        logger.info(f"Inferred Intent for '{goal}': {intent['intent']}")

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
                gatekeeper = get_gatekeeper_agent()
                blocked_channels = gatekeeper.get_blocked_channels()
                score, reasoning, debug_info = compute_simple_score(video_url, goal, transcript=transcript, intent=intent, blocked_channels=blocked_channels)
            
            logger.info(f"/score/simple {video_url} {mode} -> {score}")
            return jsonify({
                "score": score, 
                "mode": mode,
                "video_url": video_url,
                "goal": goal,
                "debug_details": debug_info,
                "intent": intent.get('intent', 'General')
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





@app.route('/audit', methods=['POST'])
def audit_video():
    """
    Auditor Agent endpoint - Content verification and clickbait detection.
    POST /audit
    Body: {
        "video_id": "...",
        "title": "...",
        "description": "...",
        "goal": "..."
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
            goal=goal
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

@app.route('/librarian/chat', methods=['POST'])
def librarian_chat():
    """
    Librarian Agent endpoint - RAG Chat.
    POST /librarian/chat
    Body: { "query": "..." }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        query = data.get('query')
        
        if not query:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "query is required",
                400,
                {'missing_field': 'query'}
            )
            
        librarian = get_librarian_agent()
        response = librarian.chat(query)
        
        return jsonify({
            'success': True,
            'response': response
        }), 200
        
    except Exception as e:
        logger.error(f"/librarian/chat error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Librarian chat failed",
            500,
            {'error_details': str(e)}
        )

@app.route('/navigator/chapters', methods=['POST'])
def navigator_get_chapters():
    """
    Navigator Agent endpoint - Get video chapters.
    POST /navigator/chapters
    Body: { "video_id": "..." }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_id = data.get('video_id')
        
        if not video_id:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "video_id is required",
                400,
                {'missing_field': 'video_id'}
            )
            
        navigator = get_navigator_agent()
        result = navigator.get_chapters(video_id)
        
        return jsonify({
            'success': True,
            'result': result
        }), 200
        
    except Exception as e:
        logger.error(f"/navigator/chapters error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Navigator chapters failed",
            500,
            {'error_details': str(e)}
        )

@app.route('/gatekeeper/filter', methods=['POST'])
def gatekeeper_filter():
    """
    Gatekeeper Agent endpoint - Filter recommendations.
    POST /gatekeeper/filter
    Body: { 
        "goal": "...", 
        "videos": [ {"id": "...", "title": "..."}, ... ] 
    }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        goal = data.get('goal')
        videos = data.get('videos', [])
        
        if not goal:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "goal is required",
                400,
                {'missing_field': 'goal'}
            )
            
        if not videos:
            return jsonify({'success': True, 'results': []}), 200
            
        # Infer Intent
        intent = get_intent_agent().infer_intent(goal)
        
        gatekeeper = get_gatekeeper_agent()
        results = gatekeeper.filter_recommendations(videos, goal, intent=intent)
        
        return jsonify({
            'success': True,
            'results': results
        }), 200
        
    except Exception as e:
        logger.error(f"/gatekeeper/filter error: {e}", exc_info=True)
        # Fail open (return empty results, frontend should probably keep videos)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Gatekeeper filtering failed",
            500,
            {'error_details': str(e)}
        )

@app.route('/gatekeeper/block_channel', methods=['POST'])
def gatekeeper_block_channel():
    """
    Block a specific channel.
    POST /gatekeeper/block_channel
    Body: { "channel_name": "..." }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        channel = data.get('channel_name')
        if not channel:
            return create_error_response(APIErrorCodes.MISSING_REQUIRED_FIELDS, "channel_name required", 400)
            
        get_gatekeeper_agent().block_channel(channel)
        return jsonify({'success': True, 'message': f'Blocked {channel}'}), 200
    except Exception as e:
         return create_error_response(APIErrorCodes.INTERNAL_ERROR, str(e), 500)

@app.route('/gatekeeper/unblock_channel', methods=['POST'])
def gatekeeper_unblock_channel():
    """
    Unblock a specific channel.
    POST /gatekeeper/unblock_channel
    Body: { "channel_name": "..." }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        channel = data.get('channel_name')
        if not channel:
            return create_error_response(APIErrorCodes.MISSING_REQUIRED_FIELDS, "channel_name required", 400)
            
        get_gatekeeper_agent().unblock_channel(channel)
        return jsonify({'success': True, 'message': f'Unblocked {channel}'}), 200
    except Exception as e:
         return create_error_response(APIErrorCodes.INTERNAL_ERROR, str(e), 500)


# ===== FIRESTORE ENDPOINTS: Persistent Storage =====



# ===== FIRESTORE ENDPOINTS: Persistent Storage =====

@app.route('/highlights', methods=['POST'])
def save_highlight():
    """
    Save a highlight to Firestore.
    POST /highlights
    """
    require_api_key()
    try:
        from firestore_service import save_highlight as fs_save_highlight
        
        data = request.get_json()
        if not data:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "Request body is required",
                400
            )
        
        # Validate required fields
        if not data.get('video_id') or data.get('timestamp') is None:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "video_id and timestamp are required",
                400
            )
        
        doc_id = fs_save_highlight(data)
        
        if doc_id:
            return jsonify({
                'success': True,
                'highlight_id': doc_id,
                'message': 'Highlight saved successfully'
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': 'Highlight saved locally only (Firestore not available)'
            }), 200
        
    except Exception as e:
        logger.error(f"/highlights POST error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to save highlight",
            500,
            {'error_details': str(e)}
        )


@app.route('/highlights', methods=['GET'])
def get_highlights():
    """
    Get all highlights.
    GET /highlights
    Query params:
      - user_id: optional user ID filter
      - limit: max results (default 100)
    """
    require_api_key()
    try:
        from firestore_service import get_highlights as fs_get_highlights
        
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 100))
        
        highlights = fs_get_highlights(user_id=user_id, limit=limit)
        
        return jsonify({
            'success': True,
            'highlights': highlights,
            'count': len(highlights)
        }), 200
        
    except Exception as e:
        logger.error(f"/highlights GET error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to retrieve highlights",
            500,
            {'error_details': str(e)}
        )


@app.route('/highlights/video/<video_id>', methods=['GET'])
def get_video_highlights(video_id):
    """
    Get all highlights for a specific video.
    GET /highlights/video/<video_id>
    """
    require_api_key()
    try:
        from firestore_service import get_highlights_for_video
        
        highlights = get_highlights_for_video(video_id)
        
        return jsonify({
            'success': True,
            'video_id': video_id,
            'highlights': highlights,
            'count': len(highlights)
        }), 200
        
    except Exception as e:
        logger.error(f"/highlights/video error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to retrieve video highlights",
            500,
            {'error_details': str(e)}
        )


@app.route('/highlights/<highlight_id>', methods=['DELETE'])
def delete_highlight(highlight_id):
    """
    Delete a highlight.
    DELETE /highlights/<highlight_id>
    """
    require_api_key()
    try:
        from firestore_service import delete_highlight as fs_delete_highlight
        
        success = fs_delete_highlight(highlight_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Highlight deleted'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Highlight not found or deletion failed'
            }), 404
        
    except Exception as e:
        logger.error(f"/highlights DELETE error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to delete highlight",
            500,
            {'error_details': str(e)}
        )


@app.route('/backup/chromadb', methods=['POST'])
def backup_chromadb():
    """
    Backup ChromaDB to Google Cloud Storage.
    POST /backup/chromadb
    """
    require_api_key()
    try:
        from firestore_service import backup_chromadb_to_gcs
        
        success = backup_chromadb_to_gcs()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'ChromaDB backup completed'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Backup failed (check logs for details)'
            }), 500
        
    except Exception as e:
        logger.error(f"/backup/chromadb error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to backup ChromaDB",
            500,
            {'error_details': str(e)}
        )


@app.route('/restore/chromadb', methods=['POST'])
def restore_chromadb():
    """
    Restore ChromaDB from Google Cloud Storage.
    POST /restore/chromadb
    """
    require_api_key()
    try:
        from firestore_service import restore_chromadb_from_gcs
        
        success = restore_chromadb_from_gcs()
        
        if success:
            # Reinitialize librarian to pick up restored data
            from librarian_agent import LibrarianAgent
            global _librarian_instance
            _librarian_instance = LibrarianAgent()
            
            return jsonify({
                'success': True,
                'message': 'ChromaDB restored successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Restore failed (no backup found or error occurred)'
            }), 500
        
    except Exception as e:
        logger.error(f"/restore/chromadb error: {e}", exc_info=True)
        return create_error_response(
            APIErrorCodes.INTERNAL_ERROR,
            "Failed to restore ChromaDB",
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

@app.route('/librarian/save', methods=['POST'])
def librarian_save_item():
    """
    Unified save endpoint.
    POST /librarian/save
    Body: {
      "video_id": "...",
      "title": "...",
      "goal": "...",
      "score": 72,
      "video_url": "...",
      "transcript": "...",   # optional
      "description": "..."   # required if transcript missing
    }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_id = data.get('video_id')
        title = data.get('title')
        goal = data.get('goal')
        score = data.get('score', 100)
        video_url = data.get('video_url', '')
        transcript = data.get('transcript', '')
        description = data.get('description', '')

        if not video_id or not title or not goal:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "video_id, title, and goal are required",
                400,
                {'missing_field': 'video_id/title/goal'}
            )

        if not transcript and not description:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "description is required when transcript is unavailable",
                400,
                {'missing_field': 'description'}
            )

        librarian = get_librarian_agent()
        result = librarian.save_video_item(
            video_id=video_id,
            title=title,
            user_goal=goal,
            score=score,
            video_url=video_url,
            transcript=transcript,
            description=description
        )

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Video saved',
                'save_mode': result.get('save_mode')
            }), 200

        return jsonify({
            'success': False,
            'error': result.get('error', 'Failed to save')
        }), 500

    except Exception as e:
        logger.error(f"/librarian/save error: {e}", exc_info=True)
        return create_error_response(APIErrorCodes.INTERNAL_ERROR, "Save failed", 500, {'error': str(e)})

@app.route('/librarian/save_summary', methods=['POST'])
def librarian_save_summary():
    """
    Persist a summary text captured from YouTube Ask panel.
    POST /librarian/save_summary
    Body: {
      "video_id": "...",
      "title": "...",
      "goal": "...",
      "summary": "...",
      "source": "youtube_ask",
      "video_url": "..."
    }
    """
    require_api_key()
    try:
        data = request.get_json(force=True)
        video_id = data.get('video_id')
        title = data.get('title')
        goal = data.get('goal')
        summary = data.get('summary')
        source = data.get('source', 'youtube_ask')
        video_url = data.get('video_url', '')

        if not video_id or not title or not goal or not summary:
            return create_error_response(
                APIErrorCodes.MISSING_REQUIRED_FIELDS,
                "video_id, title, goal, and summary are required",
                400,
                {'missing_field': 'video_id/title/goal/summary'}
            )

        librarian = get_librarian_agent()
        save_result = librarian.save_video_summary(
            video_id=video_id,
            title=title,
            user_goal=goal,
            summary=summary,
            preset=source,
            video_url=video_url
        )
        if not save_result.get('success'):
            return jsonify({'success': False, 'error': save_result.get('error', 'Failed to save summary')}), 500

        return jsonify({
            'success': True,
            'message': 'Summary saved',
            'source': source
        }), 200

    except Exception as e:
        logger.error(f"/librarian/save_summary error: {e}", exc_info=True)
        return create_error_response(APIErrorCodes.INTERNAL_ERROR, "Save summary failed", 500, {'error': str(e)})

@app.route('/librarian/saved_videos', methods=['GET'])
def librarian_get_saved_videos():
    """
    Get manually saved videos.
    GET /librarian/saved_videos
    """
    require_api_key()
    try:
        librarian = get_librarian_agent()
        videos = librarian.get_saved_videos(limit=50)
        return jsonify({'success': True, 'videos': videos}), 200
    except Exception as e:
        logger.error(f"/librarian/saved_videos error: {e}", exc_info=True)
        return create_error_response(APIErrorCodes.INTERNAL_ERROR, "Get saved videos failed", 500, {'error': str(e)})

@app.route('/librarian/get_highlights', methods=['GET'])
def librarian_get_highlights():
    """
    Get recent highlights from all videos.
    GET /librarian/get_highlights
    """
    require_api_key()
    try:
        librarian = get_librarian_agent()
        highlights = librarian.get_all_highlights(limit=50)
        return jsonify({'success': True, 'highlights': highlights}), 200
    except Exception as e:
        logger.error(f"/librarian/get_highlights error: {e}", exc_info=True)
        return create_error_response(APIErrorCodes.INTERNAL_ERROR, "Get highlights failed", 500, {'error': str(e)})

@app.route('/librarian/summaries', methods=['GET'])
def librarian_get_saved_summaries():
    """
    Get saved summaries.
    GET /librarian/summaries
    """
    require_api_key()
    try:
        librarian = get_librarian_agent()
        summaries = librarian.get_saved_summaries(limit=50)
        return jsonify({'success': True, 'summaries': summaries}), 200
    except Exception as e:
        logger.error(f"/librarian/summaries error: {e}", exc_info=True)
        return create_error_response(APIErrorCodes.INTERNAL_ERROR, "Get summaries failed", 500, {'error': str(e)})

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
        {'requested_url': request.url, 'available_endpoints': ['/health', '/score', '/feedback', '/transcript/<video_id>', '/audit', '/coach/analyze', '/coach/stats/<session_id>', '/librarian/index', '/librarian/search', '/librarian/video/<video_id>', '/librarian/stats', '/librarian/save', '/librarian/save_summary', '/librarian/summaries']}
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
