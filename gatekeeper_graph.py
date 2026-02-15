from typing import TypedDict, List, Dict, Any
import logging
import json
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GatekeeperState(TypedDict):
    videos: List[Dict]
    goal: str
    intent: Dict
    blocked_channels: List[str]
    results: List[Dict]

class GatekeeperGraph:
    def __init__(self, model_name='gemini-2.0-flash'):
        self.model = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=0,
            response_mime_type="application/json"
        )
        self.workflow = self._build_graph()

    def _filter_node(self, state: GatekeeperState):
        """Filter videos using LLM."""
        goal = state['goal']
        intent = state.get('intent')
        videos = state['videos']
        blocked_channels = state.get('blocked_channels', [])
        
        # 1. Pre-filter logic (Deterministic)
        final_results = []
        videos_to_process = []
        
        # ... Reuse logic from agent ...
        # Simplified for now: assume agent handles blocked channels passed in state? 
        # Ideally node should do it. Let's move logic here.
        
        BANNED_CATEGORIES = ['10', '20', '23', '24']
        ignored_categories = set(BANNED_CATEGORIES)
        if intent:
             if intent.get('intent') == 'Infotainment/Chill':
                 ignored_categories = {'10'} 
             elif intent.get('intent') == 'Game Dev' or 'Game' in goal:
                 ignored_categories.discard('20')

        for v in videos:
             if v.get('channel_title') in blocked_channels:
                 final_results.append({'id': v['id'], 'decision': 'blur', 'reason': 'Blocked Channel'})
                 continue
             if v.get('category_id') and str(v['category_id']) in ignored_categories:
                 final_results.append({'id': v['id'], 'decision': 'blur', 'reason': 'Distracting Category'})
                 continue
             videos_to_process.append(v)
             
        if not videos_to_process:
            return {"results": final_results}

        # 2. LLM Processing
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
- KEEP: Directly related to "{goal}", tutorials, educational, or highly relevant news.
- BLUR: Gaming, unrelated vlogs, music, drama, generic entertainment, clickbait, or topics totally unrelated to the goal.

INPUT LIST:
{video_list_str}

OUTPUT FORMAT:
Return a JSON array of objects.
[
  {{ "id": "video_id", "decision": "keep"|"blur", "reason": "short reason" }}
]
"""
        try:
            response = self.model.invoke(prompt)
            results = json.loads(response.content)
            
            result_map = {r.get('id'): r for r in results}
            for v in videos_to_process:
                vid = v['id']
                if vid in result_map:
                    final_results.append(result_map[vid])
                else:
                    final_results.append({'id': vid, 'decision': 'keep', 'reason': 'AI skipped'})
            
            return {"results": final_results}
            
        except Exception as e:
            logger.error(f"Gatekeeper Graph failed: {e}")
            # Fail open
            for v in videos_to_process:
                final_results.append({'id': v['id'], 'decision': 'keep', 'reason': 'Error'})
            return {"results": final_results}


    def _build_graph(self):
        workflow = StateGraph(GatekeeperState)
        workflow.add_node("filter", self._filter_node)
        workflow.set_entry_point("filter")
        workflow.add_edge("filter", END)
        return workflow.compile()

    def invoke(self, videos, goal, intent=None, blocked_channels=None):
        inputs = {
            "videos": videos, 
            "goal": goal, 
            "intent": intent, 
            "blocked_channels": blocked_channels or [],
            "results": []
        }
        output = self.workflow.invoke(inputs)
        return output['results']
