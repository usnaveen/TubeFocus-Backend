from typing import TypedDict, List, Dict, Any
import logging
import json
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntentState(TypedDict):
    goal: str
    taxonomy: Dict
    intent_result: Dict

class IntentGraph:
    def __init__(self, taxonomy):
        self.taxonomy = taxonomy
        self.model = ChatGoogleGenerativeAI(
            model='gemini-2.0-flash',
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=0,
            response_mime_type="application/json"
        )
        self.workflow = self._build_graph()

    def _classify_node(self, state: IntentState):
        goal = state['goal']
        taxonomy_keys = list(self.taxonomy.keys())
        
        prompt = f"""
        Classify the User's Goal into exactly one of the following Categories:
        {json.dumps(taxonomy_keys)}

        User Goal: "{goal}"

        Output JSON only: {{ "intent": "CategoryName", "confidence": 0.0-1.0 }}
        """
        
        try:
             response = self.model.invoke(prompt)
             result = json.loads(response.content)
             intent = result.get("intent", "Skill Acquisition")
             if intent not in self.taxonomy:
                 intent = "Skill Acquisition"
                 
             return {
                 "intent_result": {
                     "intent": intent,
                     "confidence": result.get("confidence", 0.5),
                     "constraints": self.taxonomy[intent],
                     "source": "langgraph_inferred"
                 }
             }
        except Exception as e:
            logger.error(f"Intent Graph failed: {e}")
            return {
                "intent_result": {
                    "intent": "Skill Acquisition", 
                    "confidence": 0, 
                    "constraints": self.taxonomy["Skill Acquisition"],
                    "source": "error_fallback"
                }
            }

    def _build_graph(self):
        wf = StateGraph(IntentState)
        wf.add_node("classify", self._classify_node)
        wf.set_entry_point("classify")
        wf.add_edge("classify", END)
        return wf.compile()

    def invoke(self, goal):
        inputs = {"goal": goal, "taxonomy": self.taxonomy, "intent_result": {}}
        out = self.workflow.invoke(inputs)
        return out['intent_result']
