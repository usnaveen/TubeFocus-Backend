from google import genai
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')


class CoachAgent:
    """
    The Coach Agent - Proactive Behavior Intervention
    
    This agent monitors user behavior and provides contextual,
    encouraging interventions based on:
    - Watch time and breaks
    - Score trends (improving/declining)
    - User's coach mode preference (strict/balanced/relaxed/custom)
    - Video completion and progress
    - Comment sentiment (optional)
    """
    
    def __init__(self):
        self.sessions = {}  # Track sessions per user/goal
        self.last_intervention = {}  # Prevent intervention spam
        self.intervention_cooldown = 120  # 2 minutes between interventions
        self.break_reminder_minutes = 60  # Default: remind after 1 hour
        self.model_name = 'gemini-2.0-flash'
        self.client = None
        if GOOGLE_API_KEY:
            self.client = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info("Coach Agent initialized")
    
    def start_session(self, session_id: str, goal: str, coach_mode: str = 'balanced',
                      custom_instructions: str = '', break_interval_minutes: int = 60):
        """
        Initialize a new coaching session.
        
        Args:
            session_id: Unique session identifier
            goal: User's learning goal
            coach_mode: 'strict', 'balanced', 'relaxed', or 'custom'
            custom_instructions: User's custom coaching instructions
            break_interval_minutes: How often to remind for breaks
        """
        self.sessions[session_id] = {
            'goal': goal,
            'coach_mode': coach_mode,
            'custom_instructions': custom_instructions,
            'break_interval_minutes': break_interval_minutes,
            'started_at': datetime.now(),
            'last_break_reminder': datetime.now(),
            'videos': [],
            'total_watch_time_seconds': 0,
            'last_score': None,
            'score_history': [],
            'is_watching': False,
            'last_activity': datetime.now(),
            'completed_videos': 0,
            'got_back_on_track': False  # Flag to track if user improved after distraction
        }
        logger.info(f"Coach started session {session_id} with mode: {coach_mode}")
        
        return {
            'message': self._get_session_start_message(goal, coach_mode),
            'type': 'session_start'
        }
    
    def _get_session_start_message(self, goal: str, coach_mode: str) -> str:
        """Generate appropriate start message based on coach mode."""
        messages = {
            'strict': f"🎯 Strict mode activated! Your goal: '{goal}'. I'll keep you laser-focused. No distractions allowed!",
            'balanced': f"👋 Let's learn! Goal: '{goal}'. I'll guide you gently while keeping you on track.",
            'relaxed': f"😌 Relaxed session for: '{goal}'. Enjoy learning at your pace. I'll just check in occasionally.",
            'custom': f"⚙️ Custom coaching for: '{goal}'. Following your instructions!"
        }
        return messages.get(coach_mode, messages['balanced'])
    
    def record_video(self, session_id: str, video_data: Dict) -> Optional[Dict]:
        """
        Record a video watched and analyze behavior.
        
        Args:
            video_data: {
                'video_id': str,
                'title': str,
                'score': float (0-100),
                'watch_duration_seconds': int,
                'completed': bool,
                'comments_sentiment': str (optional)
            }
        
        Returns:
            dict: Coach response if intervention needed, None otherwise
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        session['videos'].append({
            **video_data,
            'timestamp': datetime.now().isoformat()
        })
        session['total_watch_time_seconds'] += video_data.get('watch_duration_seconds', 0)
        session['last_activity'] = datetime.now()
        
        current_score = video_data.get('score', 50)
        session['score_history'].append(current_score)
        
        if video_data.get('completed', False):
            session['completed_videos'] += 1
        
        # Check for back on track scenario
        response = self._check_back_on_track(session, current_score)
        if response:
            return response
        
        session['last_score'] = current_score
        
        # Check various conditions
        return self._analyze_and_respond(session_id)
    
    def _check_back_on_track(self, session: Dict, current_score: float) -> Optional[Dict]:
        """Check if user got back on track after watching distracting content."""
        if session['last_score'] is None:
            return None
        
        # If previous video was low score and current is good
        if session['last_score'] < 40 and current_score >= 60:
            avg_before = sum(session['score_history'][:-1]) / max(len(session['score_history']) - 1, 1)
            avg_now = sum(session['score_history']) / len(session['score_history'])
            
            session['got_back_on_track'] = True
            
            return {
                'type': 'encouragement',
                'message_type': 'success',
                'message': f"🎉 Great job getting back on track! Your average score improved from {avg_before:.0f}% to {avg_now:.0f}%. Keep this momentum going!",
                'suggested_action': 'continue',
                'avg_score_before': avg_before,
                'avg_score_now': avg_now
            }
        
        return None
    
    def _analyze_and_respond(self, session_id: str) -> Optional[Dict]:
        """Analyze session and decide on intervention."""
        session = self.sessions[session_id]
        
        # Respect cooldown
        if self._in_cooldown(session_id):
            return None
        
        # Check break reminder first (health is priority)
        break_response = self._check_break_needed(session)
        if break_response:
            self._mark_intervention(session_id)
            return break_response
        
        # Analyze video pattern
        pattern_response = self._analyze_pattern(session)
        if pattern_response and pattern_response.get('intervention_needed'):
            self._mark_intervention(session_id)
            return pattern_response
        
        return None
    
    def _in_cooldown(self, session_id: str) -> bool:
        """Check if we're in cooldown period."""
        if session_id not in self.last_intervention:
            return False
        elapsed = (datetime.now() - self.last_intervention[session_id]).total_seconds()
        return elapsed < self.intervention_cooldown
    
    def _mark_intervention(self, session_id: str):
        """Mark that an intervention was made."""
        self.last_intervention[session_id] = datetime.now()
    
    def _check_break_needed(self, session: Dict) -> Optional[Dict]:
        """Check if user needs a break."""
        minutes_since_break = (datetime.now() - session['last_break_reminder']).total_seconds() / 60
        break_interval = session.get('break_interval_minutes', 60)
        
        if minutes_since_break >= break_interval:
            session['last_break_reminder'] = datetime.now()
            total_minutes = session['total_watch_time_seconds'] / 60
            
            return {
                'type': 'break_reminder',
                'message_type': 'break',
                'message': f"⏰ You've been learning for {total_minutes:.0f} minutes! Time for a 5-minute break. Stretch, hydrate, and come back refreshed!",
                'suggested_action': 'take_break',
                'total_watch_time_minutes': total_minutes
            }
        
        return None
    
    def _analyze_pattern(self, session: Dict) -> Dict:
        """Analyze viewing pattern and generate response."""
        videos = session['videos']
        if len(videos) < 2:
            return {'intervention_needed': False}
        
        scores = session['score_history']
        avg_score = sum(scores) / len(scores) if scores else 50
        recent_scores = scores[-5:] if len(scores) >= 5 else scores
        recent_avg = sum(recent_scores) / len(recent_scores)
        
        coach_mode = session.get('coach_mode', 'balanced')
        goal = session.get('goal', '')
        
        # Mode-specific thresholds
        thresholds = {
            'strict': {'low_score': 50, 'max_distractions': 1},
            'balanced': {'low_score': 40, 'max_distractions': 3},
            'relaxed': {'low_score': 30, 'max_distractions': 5},
            'custom': {'low_score': 40, 'max_distractions': 3}
        }
        
        threshold = thresholds.get(coach_mode, thresholds['balanced'])
        
        # Count low-score videos
        low_score_count = sum(1 for s in scores if s < threshold['low_score'])
        
        # Pattern detection
        if low_score_count > threshold['max_distractions']:
            return self._generate_refocus_message(session, avg_score, low_score_count, coach_mode)
        
        # Check for declining trend
        if len(scores) >= 4:
            first_half = scores[:len(scores)//2]
            second_half = scores[len(scores)//2:]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            
            if second_avg < first_avg - 15:  # 15 point decline
                return self._generate_trend_warning(session, first_avg, second_avg, coach_mode)
        
        # Positive reinforcement
        if len(videos) > 0 and len(videos) % 5 == 0 and avg_score >= 60:
            return {
                'type': 'encouragement',
                'message_type': 'success',
                'intervention_needed': True,
                'message': f"🌟 {session['completed_videos']} videos completed with {avg_score:.0f}% average relevance! You're making excellent progress toward '{goal[:30]}...'",
                'suggested_action': 'continue'
            }
        
        return {'intervention_needed': False}
    
    def _generate_refocus_message(self, session: Dict, avg_score: float, 
                                   distraction_count: int, coach_mode: str) -> Dict:
        """Generate a refocus message based on coach mode."""
        goal = session.get('goal', 'your goal')
        
        messages = {
            'strict': f"🚫 Focus alert! {distraction_count} off-topic videos. Your goal is '{goal[:40]}'. Get back on track NOW!",
            'balanced': f"🤔 Noticed some wandering ({distraction_count} off-topic videos). Let's refocus on '{goal[:40]}'.",
            'relaxed': f"👀 Gentle reminder: You've been exploring. When you're ready, '{goal[:40]}' is waiting!",
            'custom': session.get('custom_instructions', '') or f"Time to refocus on '{goal[:40]}'."
        }
        
        return {
            'type': 'refocus',
            'message_type': 'warning',
            'intervention_needed': True,
            'message': messages.get(coach_mode, messages['balanced']),
            'suggested_action': 'refocus',
            'avg_score': avg_score,
            'distraction_count': distraction_count
        }
    
    def _generate_trend_warning(self, session: Dict, first_avg: float, 
                                 second_avg: float, coach_mode: str) -> Dict:
        """Generate warning about declining scores."""
        if coach_mode == 'relaxed':
            return {'intervention_needed': False}  # Relaxed mode doesn't warn about trends
        
        return {
            'type': 'trend_warning',
            'message_type': 'warning',
            'intervention_needed': True,
            'message': f"📉 Your focus is drifting. Started at {first_avg:.0f}% relevance, now at {second_avg:.0f}%. Let's bring it back up!",
            'suggested_action': 'refocus',
            'trend': {'from': first_avg, 'to': second_avg}
        }
    
    def analyze_comments(self, session_id: str, video_id: str, 
                         comments: List[str]) -> Optional[Dict]:
        """
        Analyze video comments to assess content quality.
        
        Args:
            comments: List of comment texts (sample of 100)
        
        Returns:
            dict: Analysis result with recommendation
        """
        if not self.client or not comments:
            return None
        
        # Sample comments for analysis
        sample = comments[:100]
        
        prompt = f"""Analyze these YouTube comments to determine if viewers found the video helpful:

COMMENTS:
{json.dumps(sample[:50], indent=2)}

Return ONLY valid JSON:
{{
  "overall_sentiment": "positive" | "mixed" | "negative",
  "helpfulness_score": 1-10,
  "key_praise": ["specific things viewers liked"],
  "key_criticism": ["specific criticisms mentioned"],
  "recommendation": "continue" | "skip" | "skim",
  "summary": "one sentence summary"
}}"""

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            text = response.text.strip()
            if text.startswith('```'):
                text = text.replace('```json', '').replace('```', '')
            
            result = json.loads(text)
            
            # Generate user-facing message
            if result.get('helpfulness_score', 5) >= 7:
                message = f"💬 Viewers love this video! {result.get('summary', '')}"
            elif result.get('helpfulness_score', 5) <= 3:
                message = f"⚠️ Mixed reviews on this one. Consider skipping: {result.get('summary', '')}"
            else:
                message = None
            
            return {
                'video_id': video_id,
                'analysis': result,
                'message': message,
                'show_to_user': result.get('helpfulness_score', 5) >= 7 or result.get('helpfulness_score', 5) <= 3
            }
            
        except Exception as e:
            logger.error(f"Comment analysis failed: {str(e)}")
            return None
    
    def update_watch_status(self, session_id: str, is_watching: bool, 
                            current_time_seconds: int = 0):
        """Update whether user is actively watching."""
        if session_id in self.sessions:
            self.sessions[session_id]['is_watching'] = is_watching
            self.sessions[session_id]['last_activity'] = datetime.now()
            if is_watching:
                self.sessions[session_id]['total_watch_time_seconds'] = current_time_seconds
    
    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """Get comprehensive session summary."""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        scores = session['score_history']
        
        if not scores:
            return {
                'videos_watched': 0,
                'avg_score': 0,
                'total_time_minutes': 0,
                'goal': session['goal']
            }
        
        avg_score = sum(scores) / len(scores)
        total_minutes = session['total_watch_time_seconds'] / 60
        
        # Determine performance level
        if avg_score >= 70:
            performance = 'excellent'
            emoji = '🏆'
        elif avg_score >= 50:
            performance = 'good'
            emoji = '👍'
        else:
            performance = 'needs_improvement'
            emoji = '💪'
        
        return {
            'videos_watched': len(session['videos']),
            'videos_completed': session['completed_videos'],
            'avg_score': avg_score,
            'total_time_minutes': total_minutes,
            'goal': session['goal'],
            'coach_mode': session['coach_mode'],
            'performance': performance,
            'emoji': emoji,
            'highest_score': max(scores),
            'lowest_score': min(scores),
            'got_back_on_track': session.get('got_back_on_track', False),
            'summary_message': f"{emoji} {len(session['videos'])} videos watched in {total_minutes:.0f} min. Average: {avg_score:.0f}%"
        }
    
    def end_session(self, session_id: str) -> Optional[Dict]:
        """End a session and return final summary."""
        summary = self.get_session_summary(session_id)
        
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.last_intervention:
            del self.last_intervention[session_id]
        
        return summary


# Global instance (singleton pattern for agent)
_coach_instance = None

def get_coach_agent():
    """Get or create the global Coach Agent instance."""
    global _coach_instance
    if _coach_instance is None:
        _coach_instance = CoachAgent()
    return _coach_instance
