from typing import TypedDict, List, Dict, Optional
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
    focus_video_id: str
    chat_history: List[Dict]
    attached_highlight: Optional[Dict]
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

        # If a video is focused, ALWAYS ensure its source card is included
        if focus_video_id:
            focus_norm = self.agent._normalize_original_video_id(focus_video_id)
            has_focus_card = any(
                self.agent._normalize_original_video_id(c.get("video_id")) == focus_norm
                for c in source_cards
            )
            if not has_focus_card:
                focus_card = self.agent.get_video_context_card(focus_norm)
                source_cards.insert(0, focus_card)

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
        chat_history = state.get("chat_history") or []
        attached_highlight = state.get("attached_highlight")

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

        # Format source cards with rich highlight content AND transcript snippets
        if sources:
            enriched_context_lines = []
            for source in sources:
                # Include transcript snippets from the video's chunks
                snippets = source.get("snippets", [])
                snippets_text = ""
                if snippets:
                    snippets_text = "\n  ".join([f"- {s}" for s in snippets[:10]])
                    snippets_text = f"\n  Transcript Excerpts:\n  {snippets_text}"

                highlights = source.get("highlights", [])
                highlight_parts = []
                for h in highlights[:6]:
                    rl = h.get('range_label', '')
                    note = (h.get('note') or '').strip()
                    transcript = (h.get('transcript') or '').strip()
                    parts = []
                    if rl:
                        parts.append(f"[{rl}]")
                    if note:
                        parts.append(f'Note: "{note}"')
                    if transcript:
                        parts.append(f"Content: {transcript[:300]}")
                    elif note:
                        pass  # note already included
                    highlight_parts.append(" ".join(parts))
                highlights_text = "\n    ".join(highlight_parts) if highlight_parts else "None"
                enriched_context_lines.append(
                    f"Video Card: {source.get('title', 'Untitled')}\n"
                    f"  Description: {source.get('description', '')}\n"
                    f"  Summary: {source.get('summary', '')}"
                    f"{snippets_text}\n"
                    f"  Highlights:\n    {highlights_text}"
                )
            enriched_context = "\n\n".join(enriched_context_lines)
        else:
            enriched_context = "No video cards were built."

        # Format saved videos with content preview
        if saved_videos:
            inventory_lines = []
            for video in saved_videos[:30]:
                line = (
                    f"- {video.get('title', 'Untitled')} | id: {video.get('video_id', '')} "
                    f"| description: {video.get('description', '')}"
                )
                # Include summary/content preview if available from source card
                summary = video.get('summary', '')
                if summary:
                    line += f" | summary: {summary[:200]}"
                inventory_lines.append(line)
            inventory_context = "\n".join(inventory_lines)
        else:
            inventory_context = "No saved videos were retrieved."

        # Format highlights with BOTH note AND transcript content
        if inventory_highlights:
            highlight_lines = []
            for h in inventory_highlights[:30]:
                video_title = h.get("video_title") or h.get("title") or "Untitled"
                label = h.get("range_label") or ""
                note = (h.get("note") or "").strip()
                transcript = (h.get("transcript") or "").strip()
                created_at = h.get("created_at") or ""

                line = f"- {video_title} [{label}]"
                if created_at:
                    line += f" (created: {created_at[:16]})"
                if note:
                    line += f'\n  Note: "{note}"'
                if transcript:
                    line += f"\n  Transcript content: {transcript[:300]}"
                elif not note:
                    line += "\n  (no note or transcript)"
                highlight_lines.append(line)
            highlights_context = "\n".join(highlight_lines)
        else:
            highlights_context = "No highlights were retrieved."

        # Format attached highlight (when user clicks/drags a highlight into chat)
        attached_context = ""
        if attached_highlight:
            ah = attached_highlight
            attached_context = (
                f"\n\nAttached Highlight (the user is asking specifically about this highlight):\n"
                f"  Video: {ah.get('video_title', 'Unknown')}\n"
                f"  Time Range: {ah.get('range_label', 'Unknown')}\n"
                f"  User Note: {ah.get('note', '(none)')}\n"
                f"  Transcript Content: {ah.get('transcript', '(no transcript available)')}\n"
            )

        # System Prompt
        system_msg = """You are the TubeFocus Librarian — an AI assistant that helps users recall and understand their saved YouTube video content and highlights.

You have access to the user's saved library context below. Use it to answer their questions.

## Core Rules
- Answer the user's question directly first (1-3 sentences), then add short evidence bullets if helpful.
- If a focused video is present, prioritize that video unless the context clearly points elsewhere.
- For inventory/list/count questions, use the Saved Videos Inventory and Inventory Highlights sections.
- Never claim "no saved videos" if Saved Videos Inventory has items.
- Include highlight time ranges when referencing specific moments.
- Keep responses concise and practical.
- **Format your response using Markdown**:
    - Use **bold** for key concepts and terms.
    - Use bullet points for lists.
    - Use `### Headers` to organize sections if the answer is long.

## Highlight Queries
- The Inventory Highlights section contains BOTH user notes AND actual transcript content for each highlight.
- When asked "what are my highlights" or "summarize my highlights", synthesize ALL highlights into a coherent summary grouped by video.
- When asked "what was my recent/last highlight about", look at the most recent entries (sorted by creation date) and describe their transcript content.
- When an Attached Highlight is present, the user is asking about THAT specific highlight — analyze its transcript content in depth.

## Grounding
- Make a best-effort grounded answer from partial context. Do NOT default to "I don't have enough context" or "I need more information" when ANY relevant data exists in the provided sections.
- Use available titles, summaries, snippets, transcript content, and highlight notes.
- If truly no relevant context exists, say so clearly and suggest what to save next.

## Conversation History
- Previous messages in this conversation are provided. Use them for continuity (e.g., "tell me more", "what else", references to prior answers)."""

        # Build messages array
        messages = [SystemMessage(content=system_msg)]

        # Add conversation history
        for msg in chat_history[-6:]:  # Last 6 turns (3 user + 3 assistant)
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        # Current user message with full context
        user_msg = f"""Question: {query}
Focused Video ID: {focus_video_id or "none"}
{attached_context}
Context Snippets:
{context_str}

Video Cards:
{enriched_context}

Saved Videos Inventory:
{inventory_context}

Inventory Highlights:
{highlights_context}
"""

        messages.append(HumanMessage(content=user_msg))

        try:
            response = self.model.invoke(messages)
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

    def invoke(self, query: str, focus_video_id: str = "", chat_history: List[Dict] = None, attached_highlight: Dict = None):
        """Entry point for the graph."""
        inputs = {
            "query": query,
            "focus_video_id": focus_video_id or "",
            "chat_history": chat_history or [],
            "attached_highlight": attached_highlight,
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
