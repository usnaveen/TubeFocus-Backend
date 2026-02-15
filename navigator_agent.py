import re
import logging
import os
import json
from youtube_client import get_video_comments
from transcript_service import get_transcript

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

class NavigatorAgent:
    """
    The Navigator Agent - Smart Video Navigation
    
    This agent helps users navigate videos efficiently by:
    1. Extracting existing timestamps/chapters from comments (Community Wisdom).
    2. Generating smart chapters from the transcript if no comments exist (AI Generation).
    """
    
    def __init__(self):
        self.client = None
        self.model_name = 'gemini-2.0-flash'
        if GOOGLE_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=GOOGLE_API_KEY)
            except ImportError:
                logger.error("Failed to import google.genai. Install 'google-genai' package.")
            except Exception as e:
                logger.error(f"Failed to initialize Navigator client: {e}")
                
        logger.info("Navigator Agent initialized")

    def get_chapters(self, video_id):
        """
        Get chapters for a video, prioritizing comment timestamps.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            dict: {
                'source': 'comments' | 'ai_generated' | 'none',
                'chapters': [{'time': 'MM:SS', 'title': '...'}, ...],
                'error': None
            }
        """
        try:
            # 1. Try to extract from comments first (Fast, Free, Human-Verified)
            logger.info(f"Navigator looking for timestamps in comments for {video_id}...")
            comment_chapters = self._extract_from_comments(video_id)
            
            if comment_chapters:
                logger.info(f"Found {len(comment_chapters)} chapters in comments for {video_id}")
                return {
                    'source': 'comments',
                    'chapters': comment_chapters,
                    'error': None
                }
            
            # 2. Fallback to AI Generation from Transcript
            logger.info(f"No chapters in comments. Generating from transcript for {video_id}...")
            ai_chapters = self._generate_from_transcript(video_id)
            
            if ai_chapters:
                return {
                    'source': 'ai_generated',
                    'chapters': ai_chapters,
                    'error': None
                }
                
            return {
                'source': 'none',
                'chapters': [],
                'error': 'Could not extract or generate chapters'
            }

        except Exception as e:
            logger.error(f"Navigator failed for {video_id}: {str(e)}")
            return {
                'source': 'error',
                'chapters': [],
                'error': str(e)
            }

    def _extract_from_comments(self, video_id):
        """Extract timestamps from top comments."""
        try:
            comments = get_video_comments(video_id, max_results=50)
            if not comments:
                return None
                
            # Regex for timestamps: 0:00, 10:25, 1:05:30
            # Captures (Timestamp) (Title) OR (Title) (Timestamp)
            timestamp_regex = r'(?:^|\s)(\d{1,2}:\d{2}(?::\d{2})?)(?:$|\s)'
            
            best_chapter_list = []
            
            for comment in comments:
                lines = comment.split('\n')
                chapter_list = []
                
                for line in lines:
                    match = re.search(timestamp_regex, line)
                    if match:
                        timestamp = match.group(1)
                        # Clean title: remove timestamp and leading/trailing non-alphanumeric chars
                        title = line.replace(timestamp, '').strip(' -[]()')
                        if title and len(title) > 3: # Ignore empty/short titles
                            chapter_list.append({'time': timestamp, 'title': title})
                
                # Heuristic: A valid chapter list usually has at least 3 items
                if len(chapter_list) >= 3:
                     # If we find a good list, prefer the longest one
                     if len(chapter_list) > len(best_chapter_list):
                         best_chapter_list = chapter_list
            
            return best_chapter_list if best_chapter_list else None

        except Exception as e:
            logger.error(f"Error extracting comment timestamps: {e}")
            return None

    def _generate_from_transcript(self, video_id):
        """Generate chapters from transcript using Gemini."""
        if not self.client:
            logger.error("Cannot generate chapters: No GOOGLE_API_KEY")
            return None
            
        try:
            # Fetch transcript
            transcript_data = get_transcript(video_id)
            transcript_text = transcript_data.get('transcript')
            
            if not transcript_text:
                logger.warning(f"No transcript available for {video_id}")
                return None
                
            # Truncate if too long (approx 1 hour of video is fine, but super long streams might hit token limits)
            # 1 hour ~ 9000 words ~ 12k tokens. Flash handles 1M tokens, so we are safe.
            # But let's limit reasonably to avoid latency.
            if len(transcript_text) > 100000:
                transcript_text = transcript_text[:100000] + "..."
            
            prompt = f"""Generate logical video chapters with timestamps for this transcript.

TRANSCRIPT:
{transcript_text}

TASK:
Identify the key sections/topics of this video and provide a timestamp for where each starts.
The transcript doesn't have explicit timestamps, so ESTIMATE logical breakpoints based on topic shifts.
Since you don't have the exact video time, just output logical topic flow.
Wait, without timestamps in the input, you cannot hallucinate timestamps accurately.

Updated Strategy:
Analysis of the transcript text provided:
(If the transcript input above purely text without timestamps, acknowledge that you are estimating progress 0-100% or just listing topics).

Actually, the transcript service likely provides segments with timestamps.
Let's assume the previous step `get_transcript` returns text.
If I can't look at `transcript_data['segments']` which has timestamps, I can't generate accurate chapters.

Let's use the segment data if available.
"""
            # Re-thinking: Text-only transcript is bad for timestamp generation.
            # We need the segments with timestamps.
            
            segments = transcript_data.get('segments', [])
            if not segments:
                return None
                
            # Compress segments for prompt to save tokens but keep time info
            # Format: [Start] Text...
            compressed_transcript = ""
            for i, seg in enumerate(segments):
                # Sample every 15 seconds or so to reduce load? 
                # Or just dump it all since Flash 2.0 is cheap and huge context.
                # Let's dump all.
                start = int(seg['start'])
                m, s = divmod(start, 60)
                h, m = divmod(m, 60)
                time_str = f"{m:02d}:{s:02d}" if h == 0 else f"{h}:{m:02d}:{s:02d}"
                compressed_transcript += f"[{time_str}] {seg['text']}\n"

            prompt = f"""Create a concise table of contents (Chapters) for this video transcript.

TRANSCRIPT WITH TIMESTAMPS:
{compressed_transcript}

INSTRUCTIONS:
1. Identify 5-15 key topic changes.
2. Use the provided timestamps.
3. Keep chapter titles short (2-6 words).
4. Return JSON only.

JSON FORMAT:
[
  {{ "time": "0:00", "title": "Introduction" }},
  {{ "time": "MM:SS", "title": "Topic Name" }}
]
"""
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            text = response.text.strip()
            if text.startswith('```json'):
                text = text.replace('```json', '').replace('```', '')
            elif text.startswith('```'):
                text = text.replace('```', '')
                
            return json.loads(text)

        except Exception as e:
            logger.error(f"Error generating chapters with Gemini: {e}")
            return None

# Global Instance
_navigator_instance = None

def get_navigator_agent():
    global _navigator_instance
    if _navigator_instance is None:
        _navigator_instance = NavigatorAgent()
    return _navigator_instance
