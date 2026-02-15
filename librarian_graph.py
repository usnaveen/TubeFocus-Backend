from typing import TypedDict, List, Dict, Any
import logging
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define State
class LibrarianState(TypedDict):
    query: str
    context_docs: List[Dict]
    answer: str
    sources: List[Dict]

class LibrarianGraph:
    def __init__(self, librarian_agent):
        self.agent = librarian_agent
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=0
        )
        self.workflow = self._build_graph()

    def _retrieve(self, state: LibrarianState):
        """Retrieve documents from Firestore via LibrarianAgent."""
        query = state['query']
        logger.info(f"LangGraph Retrieve: {query}")
        
        # Call the existing search method
        search_res = self.agent.search_history(query, n_results=5)
        docs = search_res.get('results', [])
        
        return {"context_docs": docs}

    def _generate(self, state: LibrarianState):
        """Generate answer using RAG."""
        query = state['query']
        docs = state['context_docs']
        
        # Format Context
        if docs:
            context_str = "\n\n".join([f"Source (Video: {d['title']}): {d['snippet']}" for d in docs])
            sources = [{"title": d['title'], "video_id": d['video_id']} for d in docs]
        else:
            context_str = "No specific video context available from calculation."
            sources = []

        # Prompt
        system_msg = """You are the TubeFocus Librarian, a knowledgeable assistant.
        
        Your primary job is to answer based on the User's Video Library context provided.
        - If the user asks about videos/content and Context is empty, say you couldn't find relevant info in their library.
        - If the user says "Hi", "Hello", or asks generally "What can you do?", answer helpfully and politely without needing context.
        - Your capabilities: You can search their saved videos, specific topics, and summarize content.
        
        Be concise and helpful."""
        
        user_msg = f"""Question: {query}
        
        Context:
        {context_str}
        """

        try:
            response = self.model.invoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=user_msg)
            ])
            return {"answer": response.content, "sources": sources}
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return {"answer": "Sorry, I encountered an error generating the response.", "sources": []}

    def _build_graph(self):
        """Build the LangGraph workflow."""
        workflow = StateGraph(LibrarianState)

        # Add Nodes
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("generate", self._generate)

        # Add Edges
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    def invoke(self, query: str):
        """Entry point for the graph."""
        inputs = {"query": query, "context_docs": [], "answer": "", "sources": []}
        result = self.workflow.invoke(inputs)
        return {
            "answer": result.get("answer"),
            "sources": result.get("sources")
        }
