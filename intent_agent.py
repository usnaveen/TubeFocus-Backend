import logging
import json
import re
from config import Config
from intent_graph import IntentGraph

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntentAgent:
    """
    Classifies user goals into specific learning archetypes (Intents)
    to provide context-aware scoring constraints.
    """
    
    INTENT_TAXONOMY = {
        "Exam Prep": "Strict. High penalty for tangents, history, or long intros. Focus on core concepts and problem solving.",
        "Course/Playlist Completion": "Linear focus. Penalize videos not in sequence or unrelated to the specific course topic.",
        "Concept Introduction": "Lenient. Allow broad overviews and high-level explanations. Avoid overly dense technical details.",
        "Roadmap/Guidance": "Meta-learning focus. Prioritize 'how to learn', 'pathways', and 'mistakes to avoid'.",
        "Interview Prep": "High specificity. Focus on LeetCode, system design, star method, and common interview questions.",
        "Problem Solving": "highly specific. User wants a solution to a specific error or bug. Penalize general theory.",
        "Skill Acquisition": "Deep dive. Focus on tutorials, hands-on practice, and structured learning.",
        "Project Building": "Practical. 'How to build X'. Focus on stack-specific implementation details.",
        "Academic Research": "Formal. Prioritize lectures, papers, and theoretical depth. Penalize pop-sci.",
        "Infotainment/Chill": "Balanced. Educational but entertaining. 'Edutainment' is allowed. No brain rot."
    }

    def __init__(self):
        self.client = None
        if Config.GOOGLE_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
                self.graph = IntentGraph(self.INTENT_TAXONOMY)
            except ImportError:
                logger.error("Failed to import google.genai")
            except Exception as e:
                logger.error(f"IntentAgent init error: {e}")
        else:
            logger.warning("IntentAgent initialized without GOOGLE_API_KEY")

    def infer_intent(self, goal: str) -> dict:
        """
        Infers the intent from the user's goal string.
        Returns a dict with 'intent', 'confidence', 'constraints'.
        """
        # 1. Check for explicit intent via @mentions (e.g., "@Exam Prep Calculus")
        explicit_match = re.search(r'@([\w\s/]+)', goal)
        if explicit_match:
            potential_intent = explicit_match.group(1).strip()
            # Fuzzy match or direct lookup could go here, but let's try direct first
            for key in self.INTENT_TAXONOMY:
                if key.lower() == potential_intent.lower():
                    logger.info(f"Explicit intent detected: {key}")
                    return {
                        "intent": key,
                        "confidence": 1.0,
                        "constraints": self.INTENT_TAXONOMY[key],
                        "source": "explicit"
                    }

        # 2. AI Inference
        if not self.client:
            return self._get_default_intent()

        try:
            return self.graph.invoke(goal)
        except Exception as e:
            logger.error(f"Intent inference failed: {e}")
            return self._get_default_intent()

    def _get_default_intent(self):
        return {
            "intent": "Skill Acquisition",
            "confidence": 0.0,
            "constraints": self.INTENT_TAXONOMY["Skill Acquisition"],
            "source": "default"
        }

# Singleton access
_intent_agent = None
def get_intent_agent():
    global _intent_agent
    if _intent_agent is None:
        _intent_agent = IntentAgent()
    return _intent_agent
