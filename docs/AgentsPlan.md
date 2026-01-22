# TubeFocus: Agentic Architecture Plan

This document outlines the roadmap for evolving TubeFocus from a simple "scoring API" into a multi-agent system that actively helps the user stay focused and achieve their learning goals.

## 1. Vision
TubeFocus currently operates as a passive filter—scoring videos upon request. The goal is to transition to an **Agentic Guardrail** that understands context, verifies content depth, and actively coaches the user.

## 2. Agent Swarm Architecture

We will decompose the system into specialized agents with distinct responsibilities and latency budgets.

### 🕵️ The Gatekeeper (Latency-Critical Agent)
*   **Role**: Real-time decision maker. "Should the user watch this *right now*?"
*   **Input**: Video Title, Thumbnail (future), Description, User's Current Goal.
*   **Latency Target**: < 400ms.
*   **Model**: Gemini 2.0 Flash (Optimized/Cached).
*   **Current Status**: **Implemented** (`/score/simple`).

### 🧠 The Auditor (Deep Analysis Agent)
*   **Role**: Content verification. "Does this video actually deliver on its promise?"
*   **Input**: Full Video Transcript, Chapter Markers.
*   **Trigger**: Triggered asynchronously when a user clicks a video or hovers for >2s.
*   **Capabilities**:
    *   **Clickbait Detection**: Mismatch between Title promise and Transcript reality.
    *   **Density Scoring**: Information-per-minute analysis (detecting "fluff").
    *   **Code Extraction**: Identifying if a coding tutorial has actual code or just slides.
*   **Current Status**: **In Progress** (Transcript extraction logic added to extension).

### 🗄️ The Librarian (Memory Agent)
*   **Role**: Long-term retention and synthesis.
*   **Input**: History of "High Score" watched videos.
*   **Capabilities**:
    *   **Knowledge Graph**: Linking concepts across different videos (e.g., "This React video builds on the JS closure video you watched yesterday").
    *   **Search**: Natural language search over *watched* content ("Where did I see that specific sorting algorithm?").
    *   **Vector Database**: Storing embeddings of transcripts.

### 📣 The Coach (Proactive Agent)
*   **Role**: Behavior modification and encouragement.
*   **Trigger**: Session timeouts, doom-scrolling patterns.
*   **Capabilities**:
    *   **Intervention**: "You've watched 3 videos on 'Planning' but haven't opened VS Code. Time to build?"
    *   **Summary Generation**: detailed notes/summaries of watched sessions.

## 3. Implementation Phases

### Phase 1: Deepening the Eye (Current)
-   [x] Enable DOM-based transcript extraction in Chrome Extension.
-   [x] Update Backend to accept transcripts.
-   [ ] **Next**: Tune "The Auditor" prompt to penalize low-density content.

### Phase 2: Building the Memory
-   [ ] Setup Vector Store (Pinecone or local ChromaDB in container).
-   [ ] Pipeline: `Transcript -> Chunking -> Embedding -> Storage`.

### Phase 3: Active Coaching
-   [ ] Interface for "Chat with my History".
-   [ ] Proactive notifications/reminders in Extension.

## 4. Technical Stack
-   **Orchestration**: Python/Flask (Current). Potential migration to LangGraph for complex flows.
-   **Models**: Gemini 2.0 Flash (Fast), Gemini 1.5 Pro (Deep Context).
-   **Storage**: Redis (Hot Cache), Vector DB (Long Term).
