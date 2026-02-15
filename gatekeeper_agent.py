import logging
import os
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

class GatekeeperAgent:
    """
    The Gatekeeper Agent - Guardian of Attention
    
    This agent filters sidebar recommendations in real-time to ensure
    users only see content relevant to their current goal.
    """
    
    def __init__(self):
        self.client = None
        self.model_name = 'gemini-2.0-flash'
        if GOOGLE_API_KEY:
             try:
                 from google import genai
                 self.client = genai.Client(api_key=GOOGLE_API_KEY)
             except ImportError:
                 logger.error("Failed to import google.genai")
             except Exception as e:
                 logger.error(f"Gatekeeper init error: {e}")
                 
        self.blocked_channels = set()
        # Initialize Graph
        try:
            from gatekeeper_graph import GatekeeperGraph
            self.graph = GatekeeperGraph()
        except Exception as e:
            logger.error(f"Failed to init GatekeeperGraph: {e}")
            self.graph = None
            
        logger.info("Gatekeeper Agent initialized")

    def block_channel(self, channel_name):
        self.blocked_channels.add(channel_name)
        
    def unblock_channel(self, channel_name):
        self.blocked_channels.discard(channel_name)
        
    def get_blocked_channels(self):
        return list(self.blocked_channels)

    def filter_recommendations(self, videos, goal, intent=None, blocked_channels=None):
        """
        Batch filter a list of video recommendations against the user's goal.
        
        Args:
            videos: List of dicts [{'id': '...', 'title': '...'}, ...]
            goal: User's learning goal string
            intent: Optional dict with 'intent' and 'constraints' from IntentAgent
            blocked_channels: Optional list of channel names to block
            
        Returns:
            list: List of dicts [{'id': '...', 'decision': 'keep'|'blur', 'reason': '...'}, ...]
        """
        if not self.client or not videos:
            return [{'id': v['id'], 'decision': 'keep', 'reason': 'Agent unavailable'} for v in videos]

        if self.graph:
            return self.graph.invoke(videos, goal, intent, blocked_channels)
            
        # Fallback to old logic if graph fails init (Legacy support)
        final_results = []
        videos_to_process = []
        
        # 1. Pre-filter based on Blocked Channels and Restricted Categories
        # Category IDs: 10 (Music), 20 (Gaming), 23 (Comedy), 24 (Entertainment)
        BANNED_CATEGORIES = ['10', '20', '23', '24']
        
        # If strict intent, we might block more? For now standard blocklist.
        # But if Intent is 'Gaming', we shouldn't block 20.
        ignored_categories = set(BANNED_CATEGORIES)
        if intent:
             if intent.get('intent') == 'Infotainment/Chill':
                 ignored_categories = {'10'} # Only block music in chill mode?
             elif intent.get('intent') == 'Game Dev' or 'Game' in goal:
                 ignored_categories.discard('20')
                 
        effective_blocked_channels = self.blocked_channels
        if blocked_channels:
            effective_blocked_channels = effective_blocked_channels.union(set(blocked_channels))

        for v in videos:
            # Check Channel Blocklist
            if v.get('channel_title') in effective_blocked_channels:
                final_results.append({'id': v['id'], 'decision': 'blur', 'reason': 'Blocked Channel'})
                continue
                
            # Check Category ID (if available in future, for now we assume frontend might send it, or we skip)
            # If backend had category_id, we'd check it here. 
            # Assuming 'category_id' key might exist in v if enriched.
            if v.get('category_id') and str(v['category_id']) in ignored_categories:
                final_results.append({'id': v['id'], 'decision': 'blur', 'reason': 'Distracting Category'})
                continue
                
            videos_to_process.append(v)

        if not videos_to_process:
            return final_results

        try:
            # Construct a batch prompt
            video_list_str = ""
            for i, v in enumerate(videos_to_process):
                video_list_str += f"{i}. [ID: {v['id']}] {v['title']} (Channel: {v.get('channel_title', 'Unknown')})\n"
            
            intent_context = ""
            if intent:
                intent_context = f"\nUser Intent: {intent.get('intent')}\nConstraints: {intent.get('constraints')}\n"

            prompt = f"""You are a strict relevance filter for a student learning about: "{goal}".
{intent_context}
TASK:
Review the following list of YouTube recommendations. 
Mark them as "keep" (relevant/helpful) or "blur" (distraction/irrelevant/clickbait).

CRITERIA:
- KEEP: Directly related to "{goal}", tutorials, educational, or highly relevant news. { 'Must strictly follow constraints.' if intent else '' }
- BLUR: Gaming, unrelated vlogs, music, drama, generic entertainment, clickbait, or topics totally unrelated to the goal.

INPUT LIST:
{video_list_str}

OUTPUT FORMAT:
Return a JSON array of objects.
[
  {{ "id": "video_id", "decision": "keep"|"blur", "reason": "short reason" }}
]
RETURN ONLY JSON.
"""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    'response_mime_type': 'application/json'
                }
            )
            
            # Parse response
            results = json.loads(response.text)
            
            # Ensure all input videos have a result (fallback if LLM misses one)
            result_map = {r.get('id'): r for r in results}
            
            for v in videos_to_process:
                vid = v['id']
                if vid in result_map:
                    final_results.append(result_map[vid])
                else:
                    # Default keeping if AI missed it
                    final_results.append({'id': vid, 'decision': 'keep', 'reason': 'AI skipped'})
                    
            return final_results

        except Exception as e:
            logger.error(f"Gatekeeper failed: {e}")
            # Fail open (keep everything) on error so we don't break UI
            # But merge with already blocked ones
            fail_open_results = [{'id': v['id'], 'decision': 'keep', 'reason': 'Error'} for v in videos_to_process]
            return final_results + fail_open_results

# Global Instance
_gatekeeper_instance = None

def get_gatekeeper_agent():
    global _gatekeeper_instance
    if _gatekeeper_instance is None:
        _gatekeeper_instance = GatekeeperAgent()
    return _gatekeeper_instance
