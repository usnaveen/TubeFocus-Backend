from typing import TypedDict, List, Dict
import logging
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define State
class LibrarianState(TypedDict):
    query: str
    focus_video_id: str
    context_docs: List[Dict]
    saved_videos: List[Dict]
    inventory_highlights: List[Dict]
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
        """Retrieve documents from Firestore via LibrarianAgent using cascading multi-tier search."""
        query = state['query']
        focus_video_id = state.get('focus_video_id') or ""
        logger.info(f"LangGraph Retrieve: {query} (focus: {focus_video_id or 'none'})")
        
        # Multi-tier retrieval: passes focus_video_id for optimized search
        search_res = self.agent.search_history(
            query, n_results=8, focus_video_id=focus_video_id or None
        )
        docs = search_res.get('results', [])
        source_cards = self.agent.build_source_cards_from_results(
            docs,
            focus_video_id=focus_video_id,
            limit=4
        )
        saved_videos = self.agent.get_saved_videos(limit=80)
        inventory_highlights = self.agent.get_all_highlights(limit=120)

        if focus_video_id:
            focus_norm = self.agent._normalize_original_video_id(focus_video_id)
            inventory_highlights = [
                h for h in inventory_highlights
                if self.agent._normalize_original_video_id(h.get("video_id")) == focus_norm
            ]

        return {
            "context_docs": docs,
            "sources": source_cards,
            "saved_videos": saved_videos[:30],
            "inventory_highlights": inventory_highlights[:30],
        }

    def _generate(self, state: LibrarianState):
        """Generate answer using RAG."""
        query = state['query']
        docs = state['context_docs']
        sources = state.get('sources', [])
        focus_video_id = state.get("focus_video_id") or ""
        saved_videos = state.get("saved_videos", [])
        inventory_highlights = state.get("inventory_highlights", [])
        
        # Format Context with tier and timestamp info
        if docs:
            context_lines = []
            for d in docs:
                tier = d.get('tier', 2)
                tier_label = {1: 'Summary', 2: 'Segment', 3: 'Clip'}.get(tier, 'Chunk')
                ts_info = ''
                if d.get('start_time') is not None:
                    ts_info = f" [{d['start_time']:.0f}s-{d.get('end_time', 0):.0f}s]"
                context_lines.append(
                    f"[{tier_label}{ts_info}] Video: {d.get('title', 'Untitled')}: {d.get('snippet', '')}"
                )
            context_str = "\n\n".join(context_lines)
        else:
            context_str = "No semantic match found from saved embeddings."

        if sources:
            enriched_context_lines = []
            for source in sources:
                highlights = source.get("highlights", [])
                highlights_text = "; ".join([
                    f"{h.get('range_label', '')}: {h.get('note', '') or h.get('transcript', '')}".strip(": ")
                    for h in highlights[:4]
                ])
                enriched_context_lines.append(
                    f"Video Card: {source.get('title', 'Untitled')} | Description: {source.get('description', '')} "
                    f"| Summary: {source.get('summary', '')} | Highlights: {highlights_text}"
                )
            enriched_context = "\n".join(enriched_context_lines)
        else:
            enriched_context = "No video cards were built."

        if saved_videos:
            inventory_lines = []
            for video in saved_videos[:30]:
                inventory_lines.append(
                    f"- {video.get('title', 'Untitled')} | id: {video.get('video_id', '')} "
                    f"| description: {video.get('description', '')}"
                )
            inventory_context = "\n".join(inventory_lines)
        else:
            inventory_context = "No saved videos were retrieved."

        if inventory_highlights:
            highlight_lines = []
            for h in inventory_highlights[:30]:
                video_title = h.get("video_title") or h.get("title") or "Untitled"
                label = h.get("range_label") or ""
                note = h.get("note") or h.get("transcript") or ""
                highlight_lines.append(f"- {video_title} [{label}] {note}".strip())
            highlights_context = "\n".join(highlight_lines)
        else:
            highlights_context = "No highlights were retrieved."

        # Prompt
        system_msg = """You are the TubeFocus Librarian.

Use only the user's saved library context.
- Answer the user's question directly first (1-3 sentences), then add short evidence bullets.
- If a focused video is present, prioritize that video unless the context clearly points elsewhere.
- For inventory/list/count questions, use the Saved Videos Inventory and Inventory Highlights sections.
- Never claim "no saved videos" if Saved Videos Inventory has items.
- Use available title, summary, snippets, and highlights. Include highlight time ranges when relevant.
- Make a best-effort grounded answer from partial context; do not default to "not enough information" when useful clues exist.
- If truly no relevant context exists, say so clearly and suggest what to save next.
- Keep responses concise and practical."""
        
        user_msg = f"""Question: {query}
Focused Video ID: {focus_video_id or "none"}
        
Context Snippets:
{context_str}

Video Cards:
{enriched_context}

Saved Videos Inventory:
{inventory_context}

Inventory Highlights:
{highlights_context}
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

    def invoke(self, query: str, focus_video_id: str = ""):
        """Entry point for the graph."""
        inputs = {
            "query": query,
            "focus_video_id": focus_video_id or "",
            "context_docs": [],
            "saved_videos": [],
            "inventory_highlights": [],
            "answer": "",
            "sources": []
        }
        result = self.workflow.invoke(inputs)
        return {
            "answer": result.get("answer"),
            "sources": result.get("sources")
        }
