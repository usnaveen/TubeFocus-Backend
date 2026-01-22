from google import genai
import logging
import json
import os
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
# if GOOGLE_API_KEY:
#    genai.configure(api_key=GOOGLE_API_KEY)

class CoachAgent:
    """
    The Coach Agent - Proactive Behavior Intervention
    
    This agent autonomously monitors user behavior patterns and provides
    proactive nudges to keep users focused on their goals.
    """
    
    def __init__(self):
        self.session_history = {}  # Track sessions per user/goal
        self.last_intervention = {}  # Prevent intervention spam
        self.intervention_cooldown = 300  # 5 minutes between interventions
        self.model_name = 'gemini-2.0-flash'
        self.client = None
        if GOOGLE_API_KEY:
            self.client = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info("Coach Agent initialized")
    
    def analyze_session(self, session_id, session_data, goal):
        """
        Autonomous session analysis and pattern detection.
        
        Args:
            session_id: Unique session identifier
            session_data: List of {video_id, title, score, timestamp}
            goal: User's stated learning goal
            
        Returns:
            dict: Pattern analysis with intervention recommendations
        """
        # Agent maintains state - store session
        self.session_history[session_id] = {
            'data': session_data,
            'goal': goal,
            'analyzed_at': datetime.now().isoformat()
        }
        
        # Check if we should intervene (respect cooldown)
        if self._should_skip_intervention(session_id):
            logger.info(f"Coach skipping intervention for {session_id} (cooldown)")
            return {
                'pattern_detected': 'cooldown',
                'intervention_needed': False,
                'message': None
            }
        
        try:
            # Agent perceives and reasons about behavior
            analysis = self._detect_patterns(session_data, goal)
            
            # Agent acts autonomously - decides if intervention is needed
            if analysis['intervention_needed']:
                self.last_intervention[session_id] = datetime.now()
                logger.info(f"Coach intervening: {analysis['pattern_detected']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Coach analysis failed: {str(e)}")
            return {
                'pattern_detected': 'error',
                'intervention_needed': False,
                'message': None,
                'error': str(e)
            }
    
    def _should_skip_intervention(self, session_id):
        """Check if we're in cooldown period."""
        if session_id not in self.last_intervention:
            return False
        
        last_time = self.last_intervention[session_id]
        elapsed = (datetime.now() - last_time).total_seconds()
        return elapsed < self.intervention_cooldown
    
    def _detect_patterns(self, session_data, goal):
        """Use Gemini to detect behavioral patterns."""
        
        # Calculate basic stats
        if not session_data:
            return {
                'pattern_detected': 'insufficient_data',
                'intervention_needed': False,
                'message': None
            }
        
        scores = [v.get('score', 50) for v in session_data]
        avg_score = sum(scores) / len(scores) if scores else 50
        video_count = len(session_data)
        
        # Prepare session summary for AI
        session_summary = []
        for v in session_data[-10:]:  # Last 10 videos
            session_summary.append({
                'title': v.get('title', 'Unknown'),
                'score': v.get('score', 50),
                'timestamp': v.get('timestamp', '')
            })
        
        prompt = f"""You are a productivity coach analyzing a user's YouTube session.

USER GOAL: {goal}

SESSION STATS:
- Videos watched: {video_count}
- Average relevance score: {avg_score:.1f}/100
- Recent videos (last 10): {json.dumps(session_summary, indent=2)}

ANALYZE FOR PATTERNS:
1. DOOM SCROLLING: Low average score (<40), many videos (>5)
2. RABBIT HOLE: Started relevant, now drifting (scores declining)
3. PLANNING PARALYSIS: Only watching tutorials, no action
4. ON TRACK: Good scores, moderate quantity
5. BINGE WATCHING: Too many videos in short time

Return ONLY valid JSON:
{{
  "pattern_detected": "doom_scrolling" | "rabbit_hole" | "on_track" | "planning_paralysis" | "binge_watching",
  "average_relevance": {avg_score:.1f},
  "intervention_needed": true | false,
  "message": "friendly, encouraging message for the user",
  "suggested_action": "take_break" | "refocus" | "bookmark_for_later" | "continue" | "start_practicing",
  "reasoning": "brief explanation of the pattern"
}}

IMPORTANT:
- Be encouraging, not judgmental
- Suggest concrete actions
- Only intervene if pattern is clear
- If user is doing well (on_track), acknowledge it but don't interrupt"""

        try:
            if not self.client:
                raise ValueError("GOOGLE_API_KEY not configured")
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            # Parse response
            text = response.text.strip()
            if text.startswith('```json'):
                text = text.replace('```json', '').replace('```', '')
            elif text.startswith('```'):
                text = text.replace('```', '')
            
            result = json.loads(text)
            
            return {
                'pattern_detected': result.get('pattern_detected', 'unknown'),
                'average_relevance': result.get('average_relevance', avg_score),
                'intervention_needed': result.get('intervention_needed', False),
                'message': result.get('message', ''),
                'suggested_action': result.get('suggested_action', 'continue'),
                'reasoning': result.get('reasoning', ''),
                'video_count': video_count,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Pattern detection error: {str(e)}")
            
            # Fallback to rule-based detection
            return self._rule_based_detection(avg_score, video_count)
    
    def _rule_based_detection(self, avg_score, video_count):
        """Fallback rule-based pattern detection."""
        
        if avg_score < 40 and video_count > 5:
            return {
                'pattern_detected': 'doom_scrolling',
                'average_relevance': avg_score,
                'intervention_needed': True,
                'message': f"You've watched {video_count} videos, but most aren't aligned with your goal. Time to refocus?",
                'suggested_action': 'refocus',
                'reasoning': 'Low average score with many videos indicates doom-scrolling',
                'video_count': video_count,
                'fallback': True
            }
        elif video_count > 8:
            return {
                'pattern_detected': 'binge_watching',
                'average_relevance': avg_score,
                'intervention_needed': True,
                'message': f"You've watched {video_count} videos! Even good content needs a break. Ready to apply what you learned?",
                'suggested_action': 'take_break',
                'reasoning': 'Too many videos in session',
                'video_count': video_count,
                'fallback': True
            }
        elif avg_score > 70 and video_count > 3:
            return {
                'pattern_detected': 'on_track',
                'average_relevance': avg_score,
                'intervention_needed': False,
                'message': f"Great job! You're staying focused with {video_count} relevant videos.",
                'suggested_action': 'continue',
                'reasoning': 'Good scores and reasonable quantity',
                'video_count': video_count,
                'fallback': True
            }
        else:
            return {
                'pattern_detected': 'normal',
                'average_relevance': avg_score,
                'intervention_needed': False,
                'message': None,
                'suggested_action': 'continue',
                'reasoning': 'Session within normal parameters',
                'video_count': video_count,
                'fallback': True
            }
    
    def get_session_stats(self, session_id):
        """Get stats for a specific session."""
        if session_id not in self.session_history:
            return None
        
        session = self.session_history[session_id]
        data = session['data']
        
        if not data:
            return {
                'video_count': 0,
                'average_score': 0,
                'goal': session['goal']
            }
        
        scores = [v.get('score', 50) for v in data]
        return {
            'video_count': len(data),
            'average_score': sum(scores) / len(scores),
            'goal': session['goal'],
            'started_at': session['analyzed_at']
        }
    
    def clear_session(self, session_id):
        """Clear a session from history."""
        if session_id in self.session_history:
            del self.session_history[session_id]
        if session_id in self.last_intervention:
            del self.last_intervention[session_id]
        logger.info(f"Coach cleared session: {session_id}")

# Global instance (singleton pattern for agent)
_coach_instance = None

def get_coach_agent():
    """Get or create the global Coach Agent instance."""
    global _coach_instance
    if _coach_instance is None:
        _coach_instance = CoachAgent()
    return _coach_instance
