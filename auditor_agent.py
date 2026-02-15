from google import genai
import logging
import json
import os
from youtube_client import get_video_comments

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

class AuditorAgent:
    """
    The Auditor Agent - Community Wisdom & Quality Verification
    
    This agent analyzes YouTube comments to determine the "Community Verdict"
    on a video, identifying dealbreakers (outdated, broken, clickbait) and
    value signals (timestamps, confirmations).
    """
    
    def __init__(self):
        self.cache = {}  # In-memory cache for analysis results
        self.model_name = 'gemini-2.0-flash'
        self.client = None
        if GOOGLE_API_KEY:
             self.client = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info("Auditor Agent initialized (Comment Analysis Mode)")
    
    def analyze_content(self, video_id, title, description, goal, transcript=None):
        """
        Analyze video quality using community wisdom (comments).
        
        Args:
            video_id: YouTube video ID
            title: Video title
            description: Video description
            goal: User's learning goal
            transcript: Ignored (legacy argument)
            
        Returns:
            dict: Analysis results with community verdict.
        """
        # Check cache first
        cache_key = f"{video_id}"
        if cache_key in self.cache:
            logger.info(f"Returning cached analysis for {video_id}")
            return self.cache[cache_key]
        
        try:
            # Fetch comments (The "Community Wisdom")
            comments = get_video_comments(video_id, max_results=30)
            
            if not comments:
                logger.info(f"No comments found for {video_id}, returning neutral verdict")
                return self._get_neutral_verdict(reason="No comments available to verify this video.")
            
            # Agent reasons: analyze comments deeply
            analysis = self._analyze_community_wisdom(title, comments, goal)
            
            # Cache the result
            self.cache[cache_key] = analysis
            
            logger.info(f"Auditor analysis complete for {video_id}: verdict={analysis['community_verdict']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Auditor analysis failed for {video_id}: {str(e)}")
            return self._get_error_verdict(str(e))
    
    def _analyze_community_wisdom(self, title, comments, goal):
        """Use Gemini to perform deep analysis of comments."""
        
        prompt = f"""You are an expert Community Auditor. specificially analyzing YouTube comments to verify if a video is worth watching or dangerous/outdated.

VIDEO TITLE: {title}
USER GOAL: {goal}

COMMENTS FROM THE COMMUNITY:
{json.dumps(comments, indent=2)}

YOUR TASK:
Perform a "Community Wisdom Analysis" to find the truth about this video.

1. FILTER NOISE: Ignore "First!", "Great vid", "Love you" type comments.
2. DETECT DEALBREAKERS (Crucial):
   - Freshness: Do people say "This is outdated in 2025", "Deprecated", "Doesn't work anymore"?
   - Safety: "Don't run this code", "Virus", "Deletes database"?
   - Deception: "Clickbait", "Title is a lie", "Video is just an ad"?
   - Quality: "Audio is terrible", "Can't read screen", "Annoying voice" (differentiate from content quality).
3. EXTRACT VALUE SIGNALS:
   - "Skipped to 4:20 for the fix".
   - "This worked perfectly for Error X".
   - "Better than the documentation".

RETURN VALID JSON ONLY:
{{
  "community_verdict": <0-100 score. 0=Dangerous/Broken, 50=Mixed/Average, 100=Gold Standard>,
  "verdict_badge": "<One of: 'Community Verified', 'Outdated', 'Controversial', 'Mixed', 'Clickbait', 'Warning'>",
  "summary": "<1 sentence summary of what the comments say>",
  "critical_warnings": ["<specific warning 1>", "<specific warning 2>"],
  "useful_tips": ["<timestamp or tip 1>", "<tip 2>"],
  "pros": ["<pro 1>", "<pro 2>"],
  "cons": ["<con 1>", "<con 2>"]
}}

IMPORTANT:
- If comments say it's OUTDATED or BROKEN, score MUST be low (<40).
- If comments are mostly "I have the same problem and this didn't fix it", score low.
- If audio/video quality is bad but info is good, score ~60-70 but note it.
"""

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
            
            # Normalize and return
            return {
                'community_verdict': int(result.get('community_verdict', 50)),
                'verdict_badge': result.get('verdict_badge', 'Mixed'),
                'summary': result.get('summary', 'No summary available'),
                'critical_warnings': result.get('critical_warnings', []),
                'useful_tips': result.get('useful_tips', []),
                'pros': result.get('pros', []),
                'cons': result.get('cons', []),
                'comment_count': len(comments),
                'status': 'success'
            }
            
        except Exception as e:
            logger.error(f"Gemini analysis error: {str(e)}")
            return self._get_error_verdict(str(e))
            
    def _get_neutral_verdict(self, reason):
        return {
            'community_verdict': 50,
            'verdict_badge': 'Unverified',
            'summary': reason,
            'critical_warnings': [],
            'useful_tips': [],
            'status': 'neutral'
        }

    def _get_error_verdict(self, error):
        return {
            'community_verdict': 50,
            'verdict_badge': 'Error',
            'summary': "Could not analyze community sentiment.",
            'critical_warnings': [],
            'useful_tips': [],
            'error': str(error),
            'status': 'error'
        }

    def clear_cache(self):
        """Clear the analysis cache."""
        self.cache = {}
        logger.info("Auditor cache cleared")

# Global instance
_auditor_instance = None

def get_auditor_agent():
    """Get or create the global Auditor Agent instance."""
    global _auditor_instance
    if _auditor_instance is None:
        _auditor_instance = AuditorAgent()
    return _auditor_instance
