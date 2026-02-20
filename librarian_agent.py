import logging
import os
import time
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional
from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from config import Config
from librarian_graph import LibrarianGraph

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Librarian Agent uses the provided API key or environment variable
# Initialization happens in __init__

# ── Caching Layers ─────────────────────────────────────────────────────
class EmbeddingCache:
    """Layer 2: In-memory cache for embedding vectors to avoid redundant API calls."""
    def __init__(self):
        self._cache = {}  # {md5_hash: embedding_vector}
        self._hits = 0
        self._misses = 0

    def get_or_compute(self, text, compute_fn, task_type='RETRIEVAL_DOCUMENT'):
        key = hashlib.md5(f"{task_type}:{text.lower().strip()}".encode()).hexdigest()
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        result = compute_fn(text, task_type)
        if result is not None:
            self._cache[key] = result
        return result

    @property
    def stats(self):
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}


class SourceCardCache:
    """Layer 3: TTL-based cache for video source cards to reduce Firestore reads."""
    def __init__(self, ttl_seconds=300):
        self._cache = {}  # {video_id: (card_data, timestamp)}
        self._ttl = ttl_seconds

    def get(self, video_id):
        if video_id in self._cache:
            card, ts = self._cache[video_id]
            if time.time() - ts < self._ttl:
                return card
            del self._cache[video_id]
        return None

    def set(self, video_id, card):
        self._cache[video_id] = (card, time.time())

    def invalidate(self, video_id):
        self._cache.pop(video_id, None)


class LibrarianAgent:
    """
    The Librarian Agent - Cloud Persistent Memory and Semantic Search using Firestore.
    Uses 3-tier hierarchical timestamp-aware chunking and cascading multi-tier retrieval.
    """
    
    def __init__(self):
        """Initialize the Librarian with Firestore client, GenAI client, and caches."""
        try:
            # Initialize Firestore Client
            self.db = firestore.Client()
            self.collection_name = "video_chunks"
            
            # Initialize GenAI Client
            self.client = None
            if Config.GOOGLE_API_KEY:
                self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
            
            # Initialize Caches
            self._embedding_cache = EmbeddingCache()
            self._source_card_cache = SourceCardCache(ttl_seconds=300)
            
            logger.info("Librarian Agent initialized with Firestore + caching")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firestore Librarian: {str(e)}")
            self.db = None
            self.client = None
            self._embedding_cache = EmbeddingCache()
            self._source_card_cache = SourceCardCache()
            
    def _get_embedding(self, text, task_type='RETRIEVAL_DOCUMENT'):
        """Generate embedding using Gemini, with caching (Layer 2)."""
        if not self.client: return None
        return self._embedding_cache.get_or_compute(text, self._compute_embedding, task_type)

    def _compute_embedding(self, text, task_type='RETRIEVAL_DOCUMENT'):
        """Raw embedding API call (uncached)."""
        try:
            # Use 'models/' prefix to route to stable v1 API (not v1beta)
            result = self.client.models.embed_content(
                model="models/text-embedding-004",
                contents=text,
                config={'task_type': task_type}
            )
            return result.embeddings[0].values
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=True)
            return None

    def _normalize_original_video_id(self, raw_video_id: Optional[str]) -> str:
        video_id = (raw_video_id or "").strip()
        if not video_id:
            return ""
        for prefix in ("saved_link_", "saved_", "summary_"):
            if video_id.startswith(prefix):
                video_id = video_id[len(prefix):]
                break
        if "_highlight_" in video_id:
            video_id = video_id.split("_highlight_", 1)[0]
        return self._extract_youtube_id(video_id)

    def _extract_youtube_id(self, raw_value: str) -> str:
        value = (raw_value or "").strip()
        if not value:
            return ""
        if "youtube.com" in value or "youtu.be" in value:
            match = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11})', value)
            if match:
                return match.group(1)
        return value

    def _youtube_urls(self, video_id: str, fallback_url: str = "") -> Dict[str, str]:
        normalized_id = self._normalize_original_video_id(video_id)
        watch_url = fallback_url or (f"https://www.youtube.com/watch?v={normalized_id}" if normalized_id else "")
        embed_url = f"https://www.youtube.com/embed/{normalized_id}" if normalized_id else ""
        thumbnail_url = f"https://i.ytimg.com/vi/{normalized_id}/hqdefault.jpg" if normalized_id else ""
        return {
            "watch_url": watch_url,
            "embed_url": embed_url,
            "thumbnail_url": thumbnail_url
        }

    def _safe_iso(self, value: Optional[str]) -> str:
        if not value:
            return ""
        return str(value)

    def get_video_context_card(self, video_id: str, fallback_title: str = "Untitled Video") -> Dict:
        """
        Build a rich video source card with summary + highlights for chat UI.
        Uses Layer 3 (SourceCardCache) to avoid redundant Firestore reads.
        """
        normalized_id = self._normalize_original_video_id(video_id)
        if not self.db or not normalized_id:
            urls = self._youtube_urls(video_id)
            return {
                "video_id": normalized_id or video_id,
                "title": fallback_title,
                "video_url": urls["watch_url"],
                "embed_url": urls["embed_url"],
                "thumbnail_url": urls["thumbnail_url"],
                "description": "",
                "summary": "",
                "highlights": []
            }

        # Check source card cache (Layer 3)
        cached = self._source_card_cache.get(normalized_id)
        if cached:
            logger.info(f"Source card cache hit for {normalized_id}")
            return cached

        saved_video_doc = None
        summary_doc = None
        snippets: List[str] = []

        try:
            docs = self.db.collection(self.collection_name) \
                .where(filter=firestore.FieldFilter("original_video_id", "==", normalized_id)) \
                .limit(120) \
                .stream()

            for doc in docs:
                data = doc.to_dict() or {}
                doc_type = data.get("type")
                chunk_index = int(data.get("chunk_index") or 0)
                if doc_type == "saved_video":
                    if saved_video_doc is None:
                        saved_video_doc = data
                    elif chunk_index == 0:
                        saved_video_doc = data
                elif doc_type == "video_summary":
                    if summary_doc is None:
                        summary_doc = data
                    else:
                        prev_indexed = self._safe_iso(summary_doc.get("indexed_at"))
                        curr_indexed = self._safe_iso(data.get("indexed_at"))
                        if curr_indexed > prev_indexed:
                            summary_doc = data

                text = (data.get("text") or "").strip()
                if text and len(snippets) < 12:
                    snippets.append(text[:500])
        except Exception as e:
            logger.warning(f"Context card query failed for {normalized_id}: {e}")

        title = (
            (saved_video_doc or {}).get("title")
            or (summary_doc or {}).get("title")
            or fallback_title
        )
        description = (saved_video_doc or {}).get("description", "")
        summary = (summary_doc or {}).get("summary") or (summary_doc or {}).get("text") or ""
        video_url = (
            (saved_video_doc or {}).get("video_url")
            or (summary_doc or {}).get("video_url")
            or ""
        )

        urls = self._youtube_urls(normalized_id, fallback_url=video_url)

        highlights: List[Dict] = []
        try:
            highlight_docs = self.db.collection("highlights") \
                .where(filter=firestore.FieldFilter("video_id", "==", normalized_id)) \
                .limit(60) \
                .stream()

            for doc in highlight_docs:
                item = doc.to_dict() or {}
                start_ts = item.get("timestamp")
                end_ts = item.get("end_timestamp")
                range_label = item.get("range_label")
                if not range_label:
                    start_str = item.get("timestamp_formatted") or str(start_ts or "")
                    end_str = item.get("end_timestamp_formatted") or str(end_ts or start_ts or "")
                    range_label = f"{start_str} - {end_str}" if start_str and end_str else start_str

                highlights.append({
                    "range_label": range_label or "",
                    "note": item.get("note", ""),
                    "transcript": item.get("transcript", ""),
                    "timestamp": start_ts,
                    "end_timestamp": end_ts
                })

            highlights.sort(key=lambda h: (h.get("timestamp") if h.get("timestamp") is not None else 10**9))
            highlights = highlights[:8]
        except Exception as e:
            logger.warning(f"Highlight enrichment failed for {normalized_id}: {e}")

        if not summary and snippets:
            summary = snippets[0]

        card = {
            "video_id": normalized_id,
            "title": title,
            "video_url": urls["watch_url"],
            "embed_url": urls["embed_url"],
            "thumbnail_url": urls["thumbnail_url"],
            "description": description,
            "summary": summary,
            "snippets": snippets,
            "highlights": highlights,
            "save_mode": (saved_video_doc or {}).get("save_mode")
        }
        # Store in source card cache (Layer 3)
        self._source_card_cache.set(normalized_id, card)
        return card

    def build_source_cards_from_results(self, results: List[Dict], focus_video_id: Optional[str] = None, limit: int = 3) -> List[Dict]:
        cards: List[Dict] = []
        seen = set()
        order: List[Dict] = []

        if focus_video_id:
            order.append({"video_id": focus_video_id, "title": "Focused Video"})

        for result in results:
            video_id = self._normalize_original_video_id(result.get("video_id"))
            if not video_id:
                continue
            order.append({"video_id": video_id, "title": result.get("title") or "Saved Video"})

        for item in order:
            vid = self._normalize_original_video_id(item.get("video_id"))
            if not vid or vid in seen:
                continue
            seen.add(vid)
            card = self.get_video_context_card(vid, fallback_title=item.get("title") or "Saved Video")
            cards.append(card)
            if len(cards) >= limit:
                break

        return cards

    def index_video(self, video_id, title, transcript, goal, score, metadata=None, segments=None):
        """
        Index a video transcript into Firestore using 3-tier hierarchical chunking.
        
        Tier 1: LLM-generated video summary (1 per video)
        Tier 2: ~90-second temporal windows (chapter-level)
        Tier 3: ~20-second windows with 10s overlap (fine-grained)
        
        If segments (timestamped) are available, uses temporal chunking.
        Falls back to character-based chunking if only flat transcript is available.
        """
        if not self.db or not self.client: return False

        try:
            if not transcript or len(transcript.strip()) == 0:
                logger.warning(f"Skipping indexing for {video_id}: No transcript")
                return False
            
            # Decide chunking strategy based on available data
            if segments and len(segments) > 0:
                tier2_chunks, tier3_chunks = self._chunk_transcript_hierarchical(segments)
                all_chunks = tier2_chunks + tier3_chunks
                logger.info(f"Hierarchical chunking: {len(tier2_chunks)} Tier-2 + {len(tier3_chunks)} Tier-3 chunks")
            else:
                # Fallback: character-based chunking (backwards compatible)
                raw_chunks = self._chunk_transcript_flat(transcript, chunk_size=500)
                all_chunks = [{
                    'text': c, 'tier': 2, 'start_time': None, 'end_time': None
                } for c in raw_chunks]
                logger.info(f"Flat chunking fallback: {len(all_chunks)} chunks")

            if not all_chunks: return False
            
            batch = self.db.batch()
            count = 0
            
            for i, chunk in enumerate(all_chunks):
                embedding = self._get_embedding(chunk['text'])
                if not embedding:
                    continue
                
                tier = chunk.get('tier', 2)
                doc_id = f"{video_id}_t{tier}_{i}"
                doc_ref = self.db.collection(self.collection_name).document(doc_id)
                
                chunk_data = {
                    "video_id": video_id,
                    "title": title,
                    "goal": goal,
                    "score": float(score),
                    "chunk_index": i,
                    "total_chunks": len(all_chunks),
                    "tier": tier,
                    "start_time": chunk.get('start_time'),
                    "end_time": chunk.get('end_time'),
                    "indexed_at": datetime.now().isoformat(),
                    "text": chunk['text'],
                    "embedding": Vector(embedding)
                }
                
                # Store parent reference for Tier 3 chunks
                if tier == 3 and chunk.get('parent_index') is not None:
                    chunk_data["parent_doc_id"] = f"{video_id}_t2_{chunk['parent_index']}"
                
                if metadata:
                    chunk_meta = metadata.copy()
                    chunk_meta.pop("type", None)
                    chunk_data.update(chunk_meta)
                
                batch.set(doc_ref, chunk_data)
                count += 1
                
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            
            if count > 0:
                batch.commit()
            
            # ── Tier 1: Generate and store a video summary ──
            self._index_tier1_summary(video_id, title, transcript, goal, score, metadata)
                
            logger.info(f"Indexed video {video_id}: {len(all_chunks)} hierarchical chunks to Firestore")
            
            # Invalidate source card cache for this video
            original_id = self._normalize_original_video_id(video_id)
            self._source_card_cache.invalidate(original_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to index video {video_id}: {str(e)}")
            return False

    def _index_tier1_summary(self, video_id, title, transcript, goal, score, metadata=None):
        """Generate and index a Tier 1 LLM summary for broad 'which video?' retrieval."""
        try:
            # Use a short excerpt for summary generation (first 3000 chars)
            excerpt = transcript[:3000]
            summary_prompt = f"Summarize this video transcript in 2-3 sentences for search indexing. Title: {title}\n\n{excerpt}"
            
            # Use Gemini to generate summary
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=summary_prompt
            )
            summary_text = response.text if response.text else f"Video: {title}. {excerpt[:200]}"
            
            # Embed and store as Tier 1
            embed_text = f"{title}. {summary_text}"
            embedding = self._get_embedding(embed_text)
            if not embedding:
                return
            
            doc_ref = self.db.collection(self.collection_name).document(f"{video_id}_t1_summary")
            chunk_data = {
                "video_id": video_id,
                "title": title,
                "goal": goal,
                "score": float(score),
                "tier": 1,
                "chunk_index": 0,
                "total_chunks": 1,
                "start_time": None,
                "end_time": None,
                "indexed_at": datetime.now().isoformat(),
                "text": summary_text,
                "summary": summary_text,
                "type": "video_summary",
                "embedding": Vector(embedding)
            }
            if metadata:
                chunk_meta = metadata.copy()
                chunk_meta.pop("type", None)
                chunk_data.update(chunk_meta)
            doc_ref.set(chunk_data)
            logger.info(f"Tier 1 summary indexed for {video_id}")
        except Exception as e:
            logger.warning(f"Tier 1 summary generation failed for {video_id}: {e}")

    def save_video_item(self, video_id, title, user_goal, score=100, video_url="", transcript="", description="", segments=None):
        """
        Unified save behavior:
        1) If transcript exists, save as transcript-backed entry (with hierarchical chunking if segments available).
        2) Otherwise, save link + user description.
        """
        if not self.db:
            return {"success": False, "error": "Librarian unavailable", "save_mode": None}

        client_available = self.client is not None
        transcript = (transcript or "").strip()
        description = (description or "").strip()

        try:
            if transcript:
                storage_video_id = f"saved_{video_id}"
                metadata = {
                    "type": "saved_video",
                    "save_mode": "transcript",
                    "manual_save": True,
                    "video_url": video_url,
                    "description": description,
                    "original_video_id": video_id
                }
                if client_available:
                    success = self.index_video(
                        video_id=storage_video_id,
                        title=title,
                        transcript=transcript,
                        goal=user_goal,
                        score=score,
                        metadata=metadata,
                        segments=segments  # Pass segments for hierarchical chunking
                    )
                    if success:
                        # Add a metadata-only chunk so title/description queries can match.
                        self._index_metadata_chunk(
                            storage_video_id,
                            title=title,
                            description=description,
                            goal=user_goal,
                            score=score,
                            video_url=video_url,
                            original_video_id=video_id
                        )
                        return {"success": True, "save_mode": "transcript"}
                    logger.warning(f"Transcript indexing failed for {video_id}; storing metadata-only fallback.")

                # Fallback persistence without embeddings so saved list still works.
                fallback_ref = self.db.collection(self.collection_name).document(f"saved_meta_{video_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
                fallback_ref.set({
                    "video_id": storage_video_id,
                    "original_video_id": video_id,
                    "title": title,
                    "goal": user_goal,
                    "score": float(score),
                    "chunk_index": 0,
                    "total_chunks": 1,
                    "indexed_at": datetime.now().isoformat(),
                    "text": transcript[:1800],
                    "type": "saved_video",
                    "save_mode": "transcript",
                    "manual_save": True,
                    "description": description,
                    "video_url": video_url,
                    "embedding_missing": True
                })
                self._source_card_cache.invalidate(video_id)
                return {"success": True, "save_mode": "transcript"}

            if not description:
                return {
                    "success": False,
                    "error": "description is required when transcript is unavailable",
                    "save_mode": None
                }

            rich_text = (
                f"Saved video link\n"
                f"Title: {title}\n"
                f"Description: {description}\n"
                f"Goal: {user_goal}\n"
                f"URL: {video_url}"
            )
            doc_ref = self.db.collection(self.collection_name).document(f"saved_link_{video_id}")
            doc_data = {
                "video_id": f"saved_link_{video_id}",
                "original_video_id": video_id,
                "title": title,
                "goal": user_goal,
                "score": float(score),
                "chunk_index": 0,
                "total_chunks": 1,
                "indexed_at": datetime.now().isoformat(),
                "text": rich_text,
                "type": "saved_video",
                "save_mode": "link_only",
                "manual_save": True,
                "description": description,
                "video_url": video_url
            }
            if client_available:
                embedding = self._get_embedding(rich_text)
                if embedding:
                    doc_data["embedding"] = Vector(embedding)
                else:
                    doc_data["embedding_missing"] = True
            else:
                doc_data["embedding_missing"] = True

            doc_ref.set(doc_data)
            self._source_card_cache.invalidate(video_id)
            return {"success": True, "save_mode": "link_only"}

        except Exception as e:
            logger.error(f"Failed to save video item {video_id}: {e}")
            return {"success": False, "error": str(e), "save_mode": None}

    def save_video_summary(self, video_id, title, user_goal, summary, preset="youtube_ask", video_url=""):
        """Persist summary text to Firestore with embeddings."""
        if not self.db:
            return {"success": False, "error": "Librarian unavailable"}

        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            doc_ref = self.db.collection(self.collection_name).document(f"summary_{video_id}_{timestamp}")
            doc_data = {
                "video_id": f"summary_{video_id}",
                "original_video_id": video_id,
                "title": title,
                "goal": user_goal,
                "score": 100.0,
                "chunk_index": 0,
                "total_chunks": 1,
                "indexed_at": datetime.now().isoformat(),
                "text": summary,
                "summary": summary,
                "summary_preset": preset,
                "video_url": video_url,
                "type": "video_summary"
            }

            if self.client:
                embed_text = f"Summary for {title}\nGoal: {user_goal}\n{summary}"
                embedding = self._get_embedding(embed_text)
                if embedding:
                    doc_data["embedding"] = Vector(embedding)
                else:
                    doc_data["embedding_missing"] = True
            else:
                doc_data["embedding_missing"] = True

            doc_ref.set(doc_data)
            self._source_card_cache.invalidate(video_id)
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to save summary for {video_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_saved_videos(self, limit=50):
        """Retrieve saved videos with deduped entries for UI listing."""
        if not self.db: return []
        
        try:
            try:
                docs = self.db.collection(self.collection_name)\
                    .where(filter=firestore.FieldFilter("type", "==", "saved_video"))\
                    .order_by("indexed_at", direction=firestore.Query.DESCENDING)\
                    .limit(max(limit * 8, 100))\
                    .stream()
                doc_list = list(docs)
            except Exception as inner_e:
                logger.warning(f"Fallback to memory sort due to index issue: {inner_e}")
                docs = self.db.collection(self.collection_name)\
                    .where(filter=firestore.FieldFilter("type", "==", "saved_video"))\
                    .limit(max(limit * 8, 400))\
                    .stream()
                doc_list = list(docs)
                doc_list.sort(key=lambda d: ((d.to_dict() or {}).get("indexed_at") or ""), reverse=True)

            by_video = {}
            for doc in doc_list:
                data = doc.to_dict()
                original_video_id = data.get('original_video_id') or data.get('video_id', '')
                original_video_id = self._normalize_original_video_id(original_video_id)
                if not original_video_id:
                    continue

                if original_video_id in by_video:
                    continue

                stored_video_id = data.get('video_id', '')
                video_url = data.get('video_url')
                if not video_url and original_video_id and not str(original_video_id).startswith(('saved_', 'saved_link_')):
                    video_url = f"https://youtube.com/watch?v={original_video_id}"
                urls = self._youtube_urls(original_video_id, fallback_url=video_url or "")

                by_video[original_video_id] = {
                    'video_id': original_video_id,
                    'stored_video_id': stored_video_id,
                    'title': data.get('title', 'Untitled Video'),
                    'goal': data.get('goal'),
                    'score': data.get('score'),
                    'indexed_at': data.get('indexed_at'),
                    'save_mode': data.get('save_mode', 'transcript'),
                    'description': data.get('description', ''),
                    'video_url': urls['watch_url'],
                    'embed_url': urls['embed_url'],
                    'thumbnail_url': urls['thumbnail_url'],
                    # Keep compatibility with existing dashboard rendering.
                    'note': data.get('description', '')
                }

                if len(by_video) >= limit:
                    break

            # Legacy fallback: older entries may not have type=saved_video.
            if not by_video:
                legacy_docs = self.db.collection(self.collection_name) \
                    .order_by("indexed_at", direction=firestore.Query.DESCENDING) \
                    .limit(max(limit * 20, 250)) \
                    .stream()

                for doc in legacy_docs:
                    data = doc.to_dict() or {}
                    raw_video_id = str(data.get('video_id') or '')
                    is_saved_candidate = (
                        data.get('manual_save') is True or
                        data.get('type') in ('saved_video', 'saved_transcript') or
                        raw_video_id.startswith('saved_') or
                        raw_video_id.startswith('saved_link_')
                    )
                    if not is_saved_candidate:
                        continue

                    original_video_id = data.get('original_video_id') or raw_video_id
                    original_video_id = self._normalize_original_video_id(original_video_id)
                    if not original_video_id or original_video_id in by_video:
                        continue

                    video_url = data.get('video_url')
                    if not video_url and original_video_id:
                        video_url = f"https://youtube.com/watch?v={original_video_id}"
                    urls = self._youtube_urls(original_video_id, fallback_url=video_url or "")

                    by_video[original_video_id] = {
                        'video_id': original_video_id,
                        'stored_video_id': raw_video_id,
                        'title': data.get('title', 'Untitled Video'),
                        'goal': data.get('goal'),
                        'score': data.get('score'),
                        'indexed_at': data.get('indexed_at'),
                        'save_mode': data.get('save_mode', 'transcript'),
                        'description': data.get('description', ''),
                        'video_url': urls['watch_url'],
                        'embed_url': urls['embed_url'],
                        'thumbnail_url': urls['thumbnail_url'],
                        'note': data.get('description', '')
                    }

                    if len(by_video) >= limit:
                        break

            # Final fallback: recover pseudo-saved videos from highlights.
            if not by_video:
                recovered = self._recover_saved_videos_from_highlights(limit=limit)
                for item in recovered:
                    by_video[item["video_id"]] = item

            return list(by_video.values())
        except Exception as e:
            logger.error(f"Failed to get saved videos: {e}")
            return []

    def _recover_saved_videos_from_highlights(self, limit=50):
        """
        Build a pseudo saved-videos list from highlights when explicit saved cards are absent.
        This keeps dashboard and chat inventory answers aligned.
        """
        if not self.db:
            return []

        try:
            highlights = self.get_all_highlights(limit=max(limit * 10, 120))
            by_video = {}
            for h in highlights:
                raw_id = h.get("video_id")
                original_video_id = self._normalize_original_video_id(raw_id)
                if not original_video_id or original_video_id in by_video:
                    continue

                video_url = h.get("video_url")
                if not video_url and original_video_id:
                    video_url = f"https://youtube.com/watch?v={original_video_id}"
                urls = self._youtube_urls(original_video_id, fallback_url=video_url or "")

                by_video[original_video_id] = {
                    "video_id": original_video_id,
                    "stored_video_id": f"highlight_{original_video_id}",
                    "title": h.get("video_title") or h.get("title") or f"Video {original_video_id}",
                    "goal": None,
                    "score": None,
                    "indexed_at": h.get("created_at") or "",
                    "save_mode": "from_highlights",
                    "description": "Recovered from highlights",
                    "video_url": urls["watch_url"],
                    "embed_url": urls["embed_url"],
                    "thumbnail_url": urls["thumbnail_url"],
                    "note": h.get("note", "")
                }
                if len(by_video) >= limit:
                    break

            return list(by_video.values())
        except Exception as e:
            logger.error(f"Failed to recover saved videos from highlights: {e}")
            return []

    def _index_metadata_chunk(self, storage_video_id: str, title: str, description: str, goal: str, score: float, video_url: str, original_video_id: str):
        """Index a metadata-only chunk so title/description queries can match."""
        if not self.db:
            return
        meta_text = " ".join([t for t in [title, description, f"Goal: {goal}"] if t]).strip()
        if not meta_text:
            return
        doc_id = f"{storage_video_id}_meta"
        doc_ref = self.db.collection(self.collection_name).document(doc_id)
        doc_data = {
            "video_id": storage_video_id,
            "original_video_id": original_video_id,
            "title": title,
            "goal": goal,
            "score": float(score),
            "chunk_index": 0,
            "total_chunks": 1,
            "indexed_at": datetime.now().isoformat(),
            "text": meta_text,
            "type": "saved_video",
            "tier": 1,
            "description": description,
            "video_url": video_url
        }
        if self.client:
            embedding = self._get_embedding(meta_text)
            if embedding:
                doc_data["embedding"] = Vector(embedding)
            else:
                doc_data["embedding_missing"] = True
        else:
            doc_data["embedding_missing"] = True
        try:
            doc_ref.set(doc_data)
            self._source_card_cache.invalidate(original_video_id)
        except Exception as e:
            logger.warning(f"Metadata chunk indexing failed for {storage_video_id}: {e}")

    def get_saved_summaries(self, limit=50):
        """Retrieve generated video summaries."""
        if not self.db: return []

        try:
            try:
                docs = self.db.collection(self.collection_name)\
                    .where(filter=firestore.FieldFilter("type", "==", "video_summary"))\
                    .order_by("indexed_at", direction=firestore.Query.DESCENDING)\
                    .limit(limit)\
                    .stream()
                doc_list = list(docs)
            except Exception as inner_e:
                logger.warning(f"Fallback to memory sort for summaries: {inner_e}")
                docs = self.db.collection(self.collection_name)\
                    .where(filter=firestore.FieldFilter("type", "==", "video_summary"))\
                    .limit(limit * 4)\
                    .stream()
                doc_list = list(docs)
                doc_list.sort(key=lambda d: ((d.to_dict() or {}).get("indexed_at") or ""), reverse=True)
                doc_list = doc_list[:limit]

            return [doc.to_dict() for doc in doc_list]
        except Exception as e:
            logger.error(f"Failed to get saved summaries: {e}")
            return []

    def get_all_highlights(self, limit=50):
        """Retrieve recent highlights across all videos."""
        if not self.db: return []
        
        try:
            # Assuming highlights are stored in a separate collection or mixed in 'video_content'
            # If they are in 'video_content', they should have type='highlight' (if we designed it that way)
            # Or if they are in a separate collection 'highlights'. 
            # Looking at api.py, it imports 'get_highlights_for_video' from 'firestore_service'.
            # Let's check firestore_service.py to be sure where highlights live.
            # Assuming for now we can query the 'highlights' collection if it exists
            # OR we effectively query key insights.
            
            # Use the 'highlights' collection if it exists, otherwise return empty
            docs = self.db.collection('highlights')\
                .order_by("created_at", direction=firestore.Query.DESCENDING)\
                .limit(limit)\
                .stream()

            highlights = []
            for doc in docs:
                data = doc.to_dict() or {}
                data["id"] = doc.id
                if not data.get("range_label"):
                    start = data.get("timestamp_formatted") or str(data.get("timestamp", ""))
                    end = data.get("end_timestamp_formatted") or str(data.get("end_timestamp", data.get("timestamp", "")))
                    data["range_label"] = f"{start} - {end}" if start and end else start
                highlights.append(data)
            return highlights
        except Exception as e:
            logger.error(f"Failed to get all highlights: {e}")
            return []

    def _is_highlight_inventory_query(self, query: str) -> bool:
        text = (query or "").lower()
        highlight_terms = ("highlight", "highlights", "note", "notes")
        inventory_terms = ("do i have", "how many", "show", "list", "any", "what are")
        return any(term in text for term in highlight_terms) and any(term in text for term in inventory_terms)

    def _is_saved_video_inventory_query(self, query: str) -> bool:
        text = (query or "").lower()
        inventory_terms = ("do i have", "how many", "show", "list", "any", "what are", "is there")
        library_terms = ("saved video", "saved videos", "library", "in my library", "in my saved", "saved")
        return any(term in text for term in inventory_terms) and any(term in text for term in library_terms)

    def _match_tokens(self, text: str) -> List[str]:
        normalized = re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())
        return [t for t in normalized.split() if len(t) > 2]

    def _infer_focus_video_from_query(self, query: str, limit: int = 80) -> Optional[str]:
        """
        Infer a likely target video from natural language.
        Example: "talk about the attention video"
        """
        q = (query or "").strip()
        if not q:
            return None
        if self._is_saved_video_inventory_query(q):
            return None

        videos = self.get_saved_videos(limit=limit)
        if not videos:
            return None

        q_tokens = self._match_tokens(q)
        if not q_tokens:
            return None
        q_set = set(q_tokens)

        token_frequency = {}
        candidate_rows = []
        for v in videos:
            title = (v.get("title") or "").strip()
            if not title:
                continue
            title_tokens = [t for t in self._match_tokens(title) if t not in {"video", "tutorial", "course"}]
            if not title_tokens:
                continue
            for t in set(title_tokens):
                token_frequency[t] = token_frequency.get(t, 0) + 1
            overlap = [t for t in title_tokens if t in q_set]
            score = sum(len(t) for t in overlap)
            if score > 0:
                candidate_rows.append(
                    {
                        "score": score,
                        "video_id": v.get("video_id"),
                        "overlap": overlap,
                    }
                )

        if not candidate_rows:
            return None

        candidate_rows.sort(key=lambda item: item["score"], reverse=True)
        top = candidate_rows[0]
        top_score = top["score"]
        top_video = top["video_id"]
        second_score = candidate_rows[1]["score"] if len(candidate_rows) > 1 else 0

        # Require a clear signal to avoid accidental focus selection.
        if top_score >= 7 and (top_score - second_score >= 2):
            return top_video

        # Short-token fallback (e.g., "git video"): only if a single overlap token
        # maps uniquely to one saved video title.
        if "video" in q_set and len(top["overlap"]) == 1:
            token = top["overlap"][0]
            if token_frequency.get(token, 0) == 1 and len(token) >= 3:
                return top_video

        return None

    def _answer_saved_video_inventory(self, query: str) -> Dict:
        videos = self.get_saved_videos(limit=120)
        if not videos:
            return {"answer": "You do not have any saved videos yet.", "sources": []}

        text = (query or "").lower()
        raw_tokens = [t for t in text.replace("'", " ").split() if len(t) > 2]
        stop = {"the", "and", "for", "with", "from", "that", "this", "have", "any", "video", "videos", "saved", "library", "in", "my", "there", "is", "are", "do", "i", "by", "about"}
        tokens = [t for t in raw_tokens if t not in stop]

        scored = []
        for v in videos:
            hay = " ".join([str(v.get("title", "")).lower(), str(v.get("description", "")).lower(), str(v.get("note", "")).lower()])
            score = sum(1 for t in tokens if t in hay)
            if score > 0 or not tokens:
                scored.append((score, v))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        if tokens:
            matches = [video for score, video in scored if score > 0]
        else:
            matches = [video for _, video in scored]

        if not matches:
            return {"answer": "I could not find matching saved videos yet.", "sources": []}

        top = matches[:3]
        lines = [f"Yes — I found {len(matches)} saved video(s) that match:"]
        for v in top:
            cue = v.get("description") or v.get("note") or ""
            cue_text = f" — {cue[:80]}" if cue else ""
            lines.append(f"- {v.get('title', 'Untitled')}{cue_text}")

        seed_results = [{"video_id": v.get("video_id"), "title": v.get("title")} for v in top if v.get("video_id")]
        cards = self.build_source_cards_from_results(seed_results, limit=3)
        return {"answer": "\n".join(lines), "sources": cards}

    def _answer_highlight_inventory(self, query: str, focus_video_id: Optional[str] = None) -> Dict:
        highlights = self.get_all_highlights(limit=120)
        if focus_video_id:
            highlights = [
                h for h in highlights
                if self._normalize_original_video_id(h.get('video_id')) == self._normalize_original_video_id(focus_video_id)
            ]

        if not highlights:
            if focus_video_id:
                return {
                    "answer": "I could not find highlights for that focused video yet.",
                    "sources": []
                }
            return {"answer": "You do not have any saved highlights yet.", "sources": []}

        by_video = {}
        for item in highlights:
            vid = self._normalize_original_video_id(item.get('video_id'))
            if not vid:
                continue
            if vid not in by_video:
                by_video[vid] = []
            by_video[vid].append(item)

        total = len(highlights)
        lines = [f"You have {total} saved highlights across {len(by_video)} videos."]

        # Summarize top videos by highlight count.
        top_videos = sorted(by_video.items(), key=lambda kv: len(kv[1]), reverse=True)[:3]
        seed_results = []
        for video_id, items in top_videos:
            title = items[0].get('video_title') or f"Video {video_id}"
            lines.append(f"- {title}: {len(items)} highlights")
            seed_results.append({"video_id": video_id, "title": title})

        answer = "\n".join(lines)
        cards = self.build_source_cards_from_results(seed_results, focus_video_id=focus_video_id, limit=3)
        return {"answer": answer, "sources": cards}

    def _looks_like_non_answer(self, answer: str) -> bool:
        text = (answer or "").lower().strip()
        if not text:
            return True
        weak_patterns = (
            "i don't have enough information",
            "not enough information",
            "could not find matching",
            "couldn't find matching",
            "no relevant saved context",
            "save videos with detailed descriptions",
            "i could not find matching saved content",
            "i don't have any saved videos",
            "i do not have any saved videos",
        )
        return any(p in text for p in weak_patterns)

    def _tokenize_query(self, query: str) -> List[str]:
        text = (query or "").lower()
        raw = [t for t in text.replace("'", " ").split() if len(t) > 2]
        stop = {
            "the", "and", "for", "with", "from", "that", "this", "have", "any",
            "video", "videos", "saved", "library", "in", "my", "there", "is",
            "are", "do", "i", "by", "about", "tell", "show", "what", "which"
        }
        return [t for t in raw if t not in stop]

    def _score_text(self, text: str, tokens: List[str]) -> int:
        hay = (text or "").lower()
        if not hay:
            return 0
        if not tokens:
            return 1
        return sum(1 for t in tokens if t in hay)

    def _build_grounded_answer_from_context(self, query: str, sources: List[Dict], results: List[Dict], focus_video_id: Optional[str] = None) -> str:
        tokens = self._tokenize_query(query)
        evidence = []

        # Result snippets from retrieval.
        for r in results or []:
            title = r.get("title") or "Saved video"
            snippet = (r.get("snippet") or "").strip()
            if not snippet:
                continue
            score = self._score_text(f"{title} {snippet}", tokens)
            evidence.append({
                "score": score,
                "text": snippet,
                "line": f"[{title}] {snippet[:180]}"
            })

        # Source-card summary + highlights.
        for s in sources or []:
            title = s.get("title") or "Saved video"
            summary = (s.get("summary") or "").strip()
            if summary:
                score = self._score_text(f"{title} {summary}", tokens)
                evidence.append({
                    "score": score,
                    "text": summary,
                    "line": f"[{title}] {summary[:180]}"
                })

            for h in (s.get("highlights") or [])[:8]:
                note_or_text = (h.get("note") or h.get("transcript") or "").strip()
                if not note_or_text:
                    continue
                range_label = (h.get("range_label") or "").strip()
                score = self._score_text(f"{title} {range_label} {note_or_text}", tokens)
                prefix = f"[{title} {range_label}]".strip()
                evidence.append({
                    "score": score,
                    "text": note_or_text,
                    "line": f"{prefix} {note_or_text[:180]}"
                })

        if not evidence:
            return "I found saved videos, but there is not enough detailed context yet to answer that precisely."

        evidence.sort(key=lambda item: item["score"], reverse=True)
        best = evidence[0]["text"]
        selected = []
        seen = set()
        for item in evidence:
            line = item["line"]
            key = line[:90].lower()
            if key in seen:
                continue
            seen.add(key)
            selected.append(line)
            if len(selected) >= 3:
                break

        direct = best[:220]
        lines = [f"Based on your saved context: {direct}"]
        for line in selected:
            lines.append(f"- {line}")
        return "\n".join(lines)

    def search_history(self, query, n_results=5, goal_filter=None, focus_video_id=None):
        """
        Cascading Multi-Tier Retrieval:
          Phase 1: Broad search across Tier 1+2 (which videos are relevant?)
          Phase 2: Drill-down into Tier 3 for matched videos (exact moments)
          Phase 3: Parent expansion (retrieve surrounding context)
        
        If focus_video_id is set, skips Phase 1 and goes straight into focused retrieval.
        """
        if not self.db:
             return {'query': query, 'results': [], 'error': 'Librarian not initialized'}

        if not self.client:
            return self._lexical_search_history(query, n_results=n_results, focus_video_id=focus_video_id)
             
        try:
            # Embed query (cached via Layer 2)
            query_embedding = self._get_embedding(query, task_type='RETRIEVAL_QUERY')
            if not query_embedding:
                return {'query': query, 'results': [], 'error': 'Embedding failed'}
            
            collection_ref = self.db.collection(self.collection_name)
            formatted_results = []
            
            if focus_video_id:
                # ── FOCUSED MODE: Directly fetch chunks for this video from Firestore ──
                logger.info(f"Focused retrieval on video: {focus_video_id}")
                focus_norm = self._normalize_original_video_id(focus_video_id)

                # Strategy A: Direct Firestore query for this video's chunks (guaranteed to find them)
                try:
                    direct_docs = collection_ref \
                        .where(filter=firestore.FieldFilter("original_video_id", "==", focus_norm)) \
                        .limit(50) \
                        .stream()
                    for doc in direct_docs:
                        data = doc.to_dict() or {}
                        text = (data.get("text") or "").strip()
                        if text:
                            formatted_results.append(self._format_search_result(data))
                except Exception as e:
                    logger.warning(f"Direct focused query failed: {e}")

                # Also try with "saved_" prefixed video_id for older entries
                if not formatted_results:
                    try:
                        saved_id = f"saved_{focus_norm}"
                        alt_docs = collection_ref \
                            .where(filter=firestore.FieldFilter("video_id", "==", saved_id)) \
                            .limit(40) \
                            .stream()
                        for doc in alt_docs:
                            data = doc.to_dict() or {}
                            text = (data.get("text") or "").strip()
                            if text:
                                formatted_results.append(self._format_search_result(data))
                    except Exception as e:
                        logger.warning(f"Alt focused query failed: {e}")

                # Strategy B: Also do vector search and filter for this video (catches semantic relevance)
                try:
                    focused_results = self._vector_search(
                        collection_ref, query_embedding, limit=n_results * 3
                    )
                    seen_snippets_focused = {r.get('snippet', '')[:80] for r in formatted_results}
                    for data in focused_results:
                        vid = self._normalize_original_video_id(
                            data.get('original_video_id', data.get('video_id'))
                        )
                        if vid == focus_norm or data.get('video_id', '').endswith(focus_norm):
                            result = self._format_search_result(data)
                            if result.get('snippet', '')[:80] not in seen_snippets_focused:
                                seen_snippets_focused.add(result.get('snippet', '')[:80])
                                formatted_results.append(result)
                except Exception as e:
                    logger.warning(f"Vector focused search supplement failed: {e}")
            else:
                # ── Phase 1: Broad retrieval (Tier 1 + 2) ──
                phase1_results = self._vector_search(
                    collection_ref, query_embedding, limit=10
                )
                
                # Identify top matched video IDs
                matched_video_ids = []
                for data in phase1_results:
                    if goal_filter and data.get('goal') != goal_filter:
                        continue
                    vid = self._normalize_original_video_id(
                        data.get('original_video_id', data.get('video_id'))
                    )
                    if vid and vid not in matched_video_ids:
                        matched_video_ids.append(vid)
                    formatted_results.append(self._format_search_result(data))
                
                # ── Phase 2: Drill-down into Tier 3 for top 3 matched videos ──
                for vid in matched_video_ids[:3]:
                    tier3_results = self._vector_search(
                        collection_ref, query_embedding, limit=4
                    )
                    for data in tier3_results:
                        result_vid = self._normalize_original_video_id(
                            data.get('original_video_id', data.get('video_id'))
                        )
                        tier = data.get('tier', 2)
                        if result_vid == vid and tier == 3:
                            result = self._format_search_result(data)
                            # Add timestamp info for jumpable results
                            result['start_time'] = data.get('start_time')
                            result['end_time'] = data.get('end_time')
                            formatted_results.append(result)
                
                # ── Phase 3: Parent expansion ──
                expanded_results = []
                seen_parents = set()
                for r in formatted_results:
                    expanded_results.append(r)
                    parent_id = r.get('parent_doc_id')
                    if parent_id and parent_id not in seen_parents:
                        seen_parents.add(parent_id)
                        try:
                            parent_doc = self.db.collection(self.collection_name).document(parent_id).get()
                            if parent_doc.exists:
                                parent_data = parent_doc.to_dict()
                                parent_result = self._format_search_result(parent_data)
                                parent_result['is_parent_context'] = True
                                expanded_results.append(parent_result)
                        except Exception:
                            pass  # Parent expansion is best-effort
                formatted_results = expanded_results
            
            # Optional lexical supplement to catch title/description matches.
            lexical = self._lexical_search_history(query, n_results=n_results, focus_video_id=focus_video_id)
            lexical_results = lexical.get('results', [])
            if lexical_results:
                formatted_results.extend(lexical_results)

            # Deduplicate by snippet content
            seen_snippets = set()
            deduped = []
            for r in formatted_results:
                snippet_key = r.get('snippet', '')[:100]
                if snippet_key not in seen_snippets:
                    seen_snippets.add(snippet_key)
                    deduped.append(r)
            formatted_results = deduped[:n_results * 2]  # Allow extra for richness
                
            if not formatted_results:
                fallback = self._lexical_search_history(query, n_results=n_results, focus_video_id=focus_video_id)
                return fallback

            logger.info(f"Multi-tier search for '{query}' returned {len(formatted_results)} results")
            return {'query': query, 'results': formatted_results}
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return self._lexical_search_history(query, n_results=n_results, focus_video_id=focus_video_id)

    def _lexical_search_history(self, query, n_results=5, focus_video_id=None):
        """
        Fallback retrieval when embeddings are unavailable or vector search fails.
        """
        if not self.db:
            return {'query': query, 'results': [], 'error': 'Librarian not initialized'}

        tokens = [t for t in query.lower().split() if len(t) > 2]
        focus_norm = self._normalize_original_video_id(focus_video_id) if focus_video_id else None

        try:
            docs = self.db.collection(self.collection_name) \
                .order_by("indexed_at", direction=firestore.Query.DESCENDING) \
                .limit(250) \
                .stream()

            scored = []
            for doc in docs:
                data = doc.to_dict() or {}
                vid = self._normalize_original_video_id(data.get('original_video_id', data.get('video_id')))
                if focus_norm and vid != focus_norm:
                    continue

                haystack = " ".join([
                    str(data.get('title', '')).lower(),
                    str(data.get('description', '')).lower(),
                    str(data.get('summary', '')).lower(),
                    str(data.get('text', '')[:600]).lower()
                ])
                score = sum(1 for token in tokens if token in haystack)
                if score <= 0 and tokens:
                    continue
                scored.append((score, data))

            scored.sort(key=lambda pair: pair[0], reverse=True)
            results = [self._format_search_result(data) for _, data in scored[: max(1, n_results)]]
            return {'query': query, 'results': results, 'fallback': 'lexical'}
        except Exception as e:
            logger.error(f"Lexical search fallback failed: {e}")
            return {'query': query, 'results': [], 'error': str(e)}

    def _vector_search(self, collection_ref, query_embedding, limit=10):
        """Execute a Firestore vector search and return raw doc dicts."""
        vector_query = collection_ref.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_embedding),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit
        )
        return [doc.to_dict() for doc in vector_query.get()]

    def _format_search_result(self, data):
        """Format a raw Firestore doc dict into a search result."""
        resolved_video_id = self._normalize_original_video_id(
            data.get('original_video_id', data.get('video_id'))
        )
        urls = self._youtube_urls(resolved_video_id, fallback_url=data.get('video_url', ''))
        text = data.get('text', '') or ''

        return {
            'video_id': resolved_video_id,
            'title': data.get('title'),
            'goal': data.get('goal'),
            'score': data.get('score'),
            'snippet': (text[:260] + '...') if len(text) > 260 else text,
            'relevance': 0.0,
            'tier': data.get('tier', 2),
            'start_time': data.get('start_time'),
            'end_time': data.get('end_time'),
            'parent_doc_id': data.get('parent_doc_id'),
            'chunk_index': data.get('chunk_index'),
            'doc_type': data.get('type', 'video_chunk'),
            'description': data.get('description', ''),
            'summary': data.get('summary', ''),
            'video_url': urls['watch_url'],
            'thumbnail_url': urls['thumbnail_url'],
            'embed_url': urls['embed_url']
        }

    def delete_video(self, video_id):
        """Delete all chunks for a video from Firestore."""
        if not self.db: return False
        
        try:
            docs = self.db.collection(self.collection_name)\
                .where(filter=firestore.FieldFilter("video_id", "==", video_id))\
                .stream()
            
            count = 0
            batch = self.db.batch()
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            
            if count > 0:
                batch.commit()
                
            logger.info(f"Deleted video {video_id} from Firestore")
            return True
        except Exception as e:
            logger.error(f"Failed to delete video {video_id}: {str(e)}")
            return False

    def get_stats(self):
        """Get minimal stats."""
        if not self.db: return {'status': 'disconnected'}
        return {'status': 'connected', 'backend': 'firestore'}

    def chat(self, query, focus_video_id: Optional[str] = None, chat_history: list = None, attached_highlight: dict = None):
        """RAG Chat Implementation using LangGraph."""
        inferred_focus = None
        effective_focus_video_id = focus_video_id
        if not effective_focus_video_id:
            # If an attached highlight has a video_id, use that as focus
            if attached_highlight and attached_highlight.get('video_id'):
                effective_focus_video_id = attached_highlight['video_id']
            else:
                inferred_focus = self._infer_focus_video_from_query(query)
                effective_focus_video_id = inferred_focus

        try:
            # Always use the LLM generation flow.
            graph = LibrarianGraph(self)
            result = graph.invoke(
                query,
                focus_video_id=effective_focus_video_id,
                chat_history=chat_history or [],
                attached_highlight=attached_highlight
            )

            # Deduplicate sources
            if 'sources' in result:
                unique_sources = {}
                for source in result['sources']:
                    key = source.get('video_id') or source.get('title')
                    if not key or key in unique_sources:
                        continue
                    unique_sources[key] = source
                result['sources'] = list(unique_sources.values())

            result["meta"] = {
                "used_llm": True,
                "focus_video_id": effective_focus_video_id,
                "inferred_focus": bool(inferred_focus)
            }

            return result
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {
                "answer": "Error processing chat via LangGraph.",
                "sources": [],
                "meta": {
                    "used_llm": False,
                    "focus_video_id": effective_focus_video_id,
                    "inferred_focus": bool(inferred_focus)
                }
            }

    # ── Chunking Strategies ─────────────────────────────────────────────

    def _chunk_transcript_flat(self, transcript, chunk_size=500):
        """Backwards-compatible flat character-based chunking."""
        return [transcript[i:i+chunk_size] for i in range(0, len(transcript), chunk_size)]

    def _chunk_transcript_hierarchical(self, segments, tier2_window=90, tier3_window=20, tier3_overlap=10):
        """
        3-Tier Timestamp-Aware Hierarchical Chunking.
        
        Uses raw YouTube transcript segments (each with 'text', 'start', 'duration')
        to create temporally-aligned chunks that preserve video timestamps.
        
        Args:
            segments: List of {'text': str, 'start': float, 'duration': float}
            tier2_window: Target duration in seconds for Tier 2 chunks (~90s)
            tier3_window: Target duration in seconds for Tier 3 chunks (~20s)
            tier3_overlap: Overlap in seconds between Tier 3 chunks (~10s)
        
        Returns:
            (tier2_chunks, tier3_chunks) each as list of dicts with
            'text', 'start_time', 'end_time', 'tier', and optionally 'parent_index'
        """
        if not segments:
            return [], []

        tier2_chunks = []
        tier3_chunks = []

        # ── Build Tier 2 chunks (~90s temporal windows) ──
        current_segs = []
        window_start = segments[0]['start'] if segments else 0

        for seg in segments:
            current_segs.append(seg)
            seg_end = seg['start'] + seg.get('duration', 0)
            window_duration = seg_end - window_start

            if window_duration >= tier2_window:
                tier2_idx = len(tier2_chunks)
                tier2_chunks.append({
                    'text': ' '.join(s['text'] for s in current_segs),
                    'start_time': round(window_start, 1),
                    'end_time': round(seg_end, 1),
                    'tier': 2
                })
                # ── Build Tier 3 sub-chunks from this window ──
                sub_chunks = self._split_sub_chunks(
                    current_segs, tier3_window, tier3_overlap, parent_index=tier2_idx
                )
                tier3_chunks.extend(sub_chunks)

                window_start = seg_end
                current_segs = []

        # Handle remaining segments
        if current_segs:
            seg_end = current_segs[-1]['start'] + current_segs[-1].get('duration', 0)
            tier2_idx = len(tier2_chunks)
            tier2_chunks.append({
                'text': ' '.join(s['text'] for s in current_segs),
                'start_time': round(window_start, 1),
                'end_time': round(seg_end, 1),
                'tier': 2
            })
            sub_chunks = self._split_sub_chunks(
                current_segs, tier3_window, tier3_overlap, parent_index=tier2_idx
            )
            tier3_chunks.extend(sub_chunks)

        logger.info(
            f"Hierarchical chunking: {len(tier2_chunks)} Tier-2 (~{tier2_window}s), "
            f"{len(tier3_chunks)} Tier-3 (~{tier3_window}s, {tier3_overlap}s overlap)"
        )
        return tier2_chunks, tier3_chunks

    def _split_sub_chunks(self, segments, window_size=20, overlap=10, parent_index=None):
        """
        Split a list of timestamped segments into overlapping Tier 3 sub-chunks.
        
        Each sub-chunk covers ~window_size seconds with ~overlap seconds shared
        with adjacent chunks. This ensures no information is lost at boundaries.
        """
        if not segments:
            return []

        sub_chunks = []
        seg_idx = 0
        window_start = segments[0]['start']

        while seg_idx < len(segments):
            chunk_segs = []
            for j in range(seg_idx, len(segments)):
                seg_end = segments[j]['start'] + segments[j].get('duration', 0)
                if seg_end - window_start > window_size and chunk_segs:
                    break
                chunk_segs.append(segments[j])

            if chunk_segs:
                end_time = chunk_segs[-1]['start'] + chunk_segs[-1].get('duration', 0)
                sub_chunks.append({
                    'text': ' '.join(s['text'] for s in chunk_segs),
                    'start_time': round(window_start, 1),
                    'end_time': round(end_time, 1),
                    'tier': 3,
                    'parent_index': parent_index
                })

            # Advance by (window_size - overlap) seconds
            step = window_size - overlap
            next_start = window_start + step
            while seg_idx < len(segments) and segments[seg_idx]['start'] < next_start:
                seg_idx += 1
            if seg_idx < len(segments):
                window_start = segments[seg_idx]['start']
            else:
                break

        return sub_chunks

# Singleton
_librarian_instance = None
def get_librarian_agent():
    global _librarian_instance
    if _librarian_instance is None:
        _librarian_instance = LibrarianAgent()
    return _librarian_instance
