import logging
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_video_id(url_or_id):
    """Extract video ID from URL or return ID if already extracted."""
    if 'youtube.com' in url_or_id or 'youtu.be' in url_or_id:
        import re
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:watch\?v=)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)
    return url_or_id

def get_transcript(video_id, languages=['en', 'en-US', 'en-GB']):
    """
    Fetch transcript for a YouTube video using the OLD stable API.
    
    This uses YouTubeTranscriptApi.get_transcript() which works on ALL versions
    including old ones that don't have list_transcripts().
    
    Args:
        video_id: YouTube video ID or URL
        languages: List of preferred language codes
        
    Returns:
        dict: {
            'transcript': str (full text),
            'segments': list (with timestamps),
            'language': str (detected language),
            'is_generated': None (old API doesn't provide this),
            'error': str (if any)
        }
    """
    try:
        video_id = extract_video_id(video_id)
        
        # Use OLD stable API: get_transcript(video_id, languages)
        # This works on ALL versions of youtube-transcript-api
        segments = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=languages
        )
        
        # Combine all segments into full text
        full_text = ' '.join([segment['text'] for segment in segments])
        
        # The old API doesn't tell us which language was used or if generated
        # We assume first language in the list
        language = languages[0] if languages else 'en'
        
        logger.info(f"Successfully fetched transcript for {video_id}")
        
        return {
            'transcript': full_text,
            'segments': segments,
            'language': language,
            'is_generated': None,  # Old API doesn't provide this
            'error': None
        }
        
    except TranscriptsDisabled:
        logger.error(f"Transcripts are disabled for video {video_id}")
        return {
            'transcript': None,
            'segments': [],
            'language': None,
            'is_generated': None,
            'error': 'Transcripts are disabled for this video'
        }
        
    except NoTranscriptFound:
        logger.warning(f"No transcript found for video {video_id} in languages {languages}")
        # Try without language restriction as fallback
        try:
            logger.info(f"Trying to fetch any available transcript for {video_id}")
            segments = YouTubeTranscriptApi.get_transcript(video_id)
            full_text = ' '.join([segment['text'] for segment in segments])
            
            return {
                'transcript': full_text,
                'segments': segments,
                'language': 'unknown',
                'is_generated': None,
                'error': None
            }
        except Exception as e:
            logger.error(f"Failed to get any transcript for {video_id}: {str(e)}")
            return {
                'transcript': None,
                'segments': [],
                'language': None,
                'is_generated': None,
                'error': f'No transcript available: {str(e)}'
            }
            
    except VideoUnavailable:
        logger.error(f"Video {video_id} is unavailable")
        return {
            'transcript': None,
            'segments': [],
            'language': None,
            'is_generated': None,
            'error': 'Video is unavailable'
        }
        
    except Exception as e:
        logger.error(f"Error fetching transcript for {video_id}: {str(e)}")
        return {
            'transcript': None,
            'segments': [],
            'language': None,
            'is_generated': None,
            'error': str(e)
        }

def get_transcript_excerpt(video_id, max_length=3000, languages=['en', 'en-US', 'en-GB']):
    """
    Get a transcript excerpt for quick analysis.
    
    Args:
        video_id: YouTube video ID or URL
        max_length: Maximum character length
        languages: List of preferred language codes
        
    Returns:
        dict: Same as get_transcript but with truncated text
    """
    result = get_transcript(video_id, languages)
    
    if result['transcript'] and len(result['transcript']) > max_length:
        result['transcript'] = result['transcript'][:max_length] + '...'
        result['truncated'] = True
    else:
        result['truncated'] = False
    
    return result
