from google import genai
import logging
import json
import os
from transcript_service import get_transcript_excerpt

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
# if GOOGLE_API_KEY:
#    genai.configure(api_key=GOOGLE_API_KEY)

class AuditorAgent:
    """
    The Auditor Agent - Content Verification and Quality Analysis
    
    This agent autonomously verifies if video content matches its promises,
    detects clickbait, and measures information density.
    """
    
    def __init__(self):
        self.cache = {}  # In-memory cache for analysis results
        self.model_name = 'gemini-2.0-flash'
        self.client = None
        if GOOGLE_API_KEY:
             self.client = genai.Client(api_key=GOOGLE_API_KEY)
        logger.info("Auditor Agent initialized")
    
    def analyze_content(self, video_id, title, description, goal, transcript=None):
        """
        Autonomous content verification and analysis.
        
        Args:
            video_id: YouTube video ID
            title: Video title
            description: Video description
            goal: User's learning goal
            transcript: Optional pre-fetched transcript
            
        Returns:
            dict: Analysis results with clickbait score, density, recommendations
        """
        # Check cache first (agent maintains state)
        cache_key = f"{video_id}:{goal}"
        if cache_key in self.cache:
            logger.info(f"Returning cached analysis for {video_id}")
            return self.cache[cache_key]
        
        try:
            # Fetch transcript if not provided (agent perceives environment)
            if not transcript:
                logger.info(f"Auditor fetching transcript for {video_id}")
                transcript_data = get_transcript_excerpt(video_id, max_length=3000)
                transcript = transcript_data.get('transcript', '')
                is_generated = transcript_data.get('is_generated', False)
                transcript_error = transcript_data.get('error')
            else:
                is_generated = False
                transcript_error = None
            
            # If no transcript available, do lighter analysis
            if not transcript or transcript_error:
                return self._analyze_without_transcript(title, description, goal, transcript_error)
            
            # Agent reasons: analyze content deeply
            analysis = self._deep_content_analysis(title, description, transcript, goal, is_generated)
            
            # Cache the result (agent maintains state)
            self.cache[cache_key] = analysis
            
            logger.info(f"Auditor analysis complete for {video_id}: clickbait={analysis['clickbait_score']}, density={analysis['density_score']}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Auditor analysis failed for {video_id}: {str(e)}")
            return {
                'clickbait_score': 50,
                'density_score': 50,
                'delivers_promise': None,
                'key_topics': [],
                'recommendation': 'unknown',
                'reasoning': f'Analysis failed: {str(e)}',
                'error': str(e)
            }
    
    def _deep_content_analysis(self, title, description, transcript, goal, is_generated):
        """Use Gemini to perform deep content analysis."""
        
        prompt = f"""You are an expert content verification agent. Analyze this YouTube video critically.

VIDEO DETAILS:
Title: {title}
Description: {description[:500]}
Transcript (first 3000 chars): {transcript[:3000]}
Transcript Type: {'Auto-generated' if is_generated else 'Manual'}

USER CONTEXT:
Learning Goal: {goal}

ANALYSIS TASKS:
1. CLICKBAIT DETECTION: Does the title promise something the content doesn't deliver?
2. INFORMATION DENSITY: How much valuable information per minute?
3. PROMISE FULFILLMENT: Does the video actually teach what the title claims?
4. KEY TOPICS: What are the main topics actually covered?
5. RELEVANCE: How relevant is this to the user's goal?

Return ONLY valid JSON:
{{
  "clickbait_score": <0-100, where 100 means definitely clickbait>,
  "density_score": <0-100, where 100 means high information density>,
  "delivers_promise": <true/false>,
  "key_topics": ["topic1", "topic2", "topic3"],
  "recommendation": "watch" | "skip" | "skim",
  "reasoning": "<2-3 sentence explanation>",
  "relevance_to_goal": <0-100>
}}

IMPORTANT: Be strict. Many videos have clickbait titles. If the title makes a big claim but the transcript is vague, that's clickbait."""

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
            
            # Validate and normalize
            return {
                'clickbait_score': int(result.get('clickbait_score', 50)),
                'density_score': int(result.get('density_score', 50)),
                'delivers_promise': result.get('delivers_promise', None),
                'key_topics': result.get('key_topics', []),
                'recommendation': result.get('recommendation', 'unknown'),
                'reasoning': result.get('reasoning', 'No reasoning provided'),
                'relevance_to_goal': int(result.get('relevance_to_goal', 50)),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Gemini analysis error: {str(e)}")
            return {
                'clickbait_score': 50,
                'density_score': 50,
                'delivers_promise': None,
                'key_topics': [],
                'recommendation': 'unknown',
                'reasoning': f'AI analysis failed: {str(e)}',
                'relevance_to_goal': 50,
                'error': str(e)
            }
    
    def _analyze_without_transcript(self, title, description, goal, transcript_error):
        """Fallback analysis when transcript is unavailable."""
        
        prompt = f"""Analyze this YouTube video based on limited information.

Title: {title}
Description: {description[:500]}
User Goal: {goal}
Note: Transcript unavailable ({transcript_error})

Return ONLY valid JSON:
{{
  "clickbait_score": <0-100>,
  "density_score": <0-100, default to 50 since we can't verify>,
  "delivers_promise": null,
  "key_topics": ["based on title/description"],
  "recommendation": "watch" | "skip" | "skim",
  "reasoning": "<brief explanation>",
  "relevance_to_goal": <0-100>
}}"""

        try:
            if not self.client:
                raise ValueError("GOOGLE_API_KEY not configured")
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            text = response.text.strip()
            if text.startswith('```json'):
                text = text.replace('```json', '').replace('```', '')
            elif text.startswith('```'):
                text = text.replace('```', '')
            
            result = json.loads(text)
            
            return {
                'clickbait_score': int(result.get('clickbait_score', 50)),
                'density_score': 50,  # Can't measure without transcript
                'delivers_promise': None,
                'key_topics': result.get('key_topics', []),
                'recommendation': result.get('recommendation', 'unknown'),
                'reasoning': f"Limited analysis (no transcript): {result.get('reasoning', '')}",
                'relevance_to_goal': int(result.get('relevance_to_goal', 50)),
                'transcript_unavailable': True,
                'error': transcript_error
            }
            
        except Exception as e:
            logger.error(f"Fallback analysis error: {str(e)}")
            return {
                'clickbait_score': 50,
                'density_score': 50,
                'delivers_promise': None,
                'key_topics': [],
                'recommendation': 'unknown',
                'reasoning': 'Unable to analyze without transcript',
                'relevance_to_goal': 50,
                'transcript_unavailable': True,
                'error': str(e)
            }
    
    def clear_cache(self):
        """Clear the analysis cache."""
        self.cache = {}
        logger.info("Auditor cache cleared")

# Global instance (singleton pattern for agent)
_auditor_instance = None

def get_auditor_agent():
    """Get or create the global Auditor Agent instance."""
    global _auditor_instance
    if _auditor_instance is None:
        _auditor_instance = AuditorAgent()
    return _auditor_instance
