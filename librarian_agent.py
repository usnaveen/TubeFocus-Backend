import logging
import os
from datetime import datetime
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

class LibrarianAgent:
    """
    The Librarian Agent - Cloud Persistent Memory and Semantic Search using Firestore.
    """
    
    def __init__(self):
        """Initialize the Librarian with Firestore client and GenAI client."""
        try:
            # Initialize Firestore Client
            self.db = firestore.Client()
            self.collection_name = "video_chunks"
            
            # Initialize GenAI Client
            self.client = None
            if Config.GOOGLE_API_KEY:
                self.client = genai.Client(api_key=Config.GOOGLE_API_KEY)
            
            logger.info("Librarian Agent initialized with Firestore")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firestore Librarian: {str(e)}")
            self.db = None
            self.client = None
            
    def _get_embedding(self, text):
        """Generate embedding using Gemini."""
        if not self.client: return None
        try:
            # Use text-embedding-004 model
            result = self.client.models.embed_content(
                model="text-embedding-004",
                contents=text,
                config={'task_type': 'RETRIEVAL_DOCUMENT'}
            )
            return result.embeddings[0].values
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def index_video(self, video_id, title, transcript, goal, score, metadata=None):
        """Index a video transcript into Firestore."""
        if not self.db or not self.client: return False

        try:
            if not transcript or len(transcript.strip()) == 0:
                logger.warning(f"Skipping indexing for {video_id}: No transcript")
                return False
            
            chunks = self._chunk_transcript(transcript, chunk_size=500)
            if not chunks: return False
            
            batch = self.db.batch()
            count = 0
            
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding = self._get_embedding(chunk)
                if not embedding:
                    continue
                
                doc_ref = self.db.collection(self.collection_name).document(f"{video_id}_{i}")
                
                chunk_data = {
                    "video_id": video_id,
                    "title": title,
                    "goal": goal,
                    "score": float(score),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "indexed_at": datetime.now().isoformat(),
                    "text": chunk, # Store text for retrieval
                    "embedding": Vector(embedding) # Store as Vector
                }
                
                if metadata:
                    chunk_data.update(metadata)
                
                batch.set(doc_ref, chunk_data)
                count += 1
                
                # Firestore batch limit is 500
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            
            if count > 0:
                batch.commit()
                
            logger.info(f"Indexed video {video_id}: {len(chunks)} chunks to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index video {video_id}: {str(e)}")
            return False

    def save_video_item(self, video_id, title, user_goal, score=100, video_url="", transcript="", description=""):
        """
        Unified save behavior:
        1) If transcript exists, save as transcript-backed entry.
        2) Otherwise, save link + user description.
        """
        if not self.db or not self.client:
            return {"success": False, "error": "Librarian unavailable", "save_mode": None}

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
                success = self.index_video(
                    video_id=storage_video_id,
                    title=title,
                    transcript=transcript,
                    goal=user_goal,
                    score=score,
                    metadata=metadata
                )
                return {"success": success, "save_mode": "transcript"}

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
            embedding = self._get_embedding(rich_text)
            if not embedding:
                return {"success": False, "error": "embedding generation failed", "save_mode": None}

            doc_ref = self.db.collection(self.collection_name).document(f"saved_link_{video_id}")
            doc_ref.set({
                "video_id": f"saved_link_{video_id}",
                "original_video_id": video_id,
                "title": title,
                "goal": user_goal,
                "score": float(score),
                "chunk_index": 0,
                "total_chunks": 1,
                "indexed_at": datetime.now().isoformat(),
                "text": rich_text,
                "embedding": Vector(embedding),
                "type": "saved_video",
                "save_mode": "link_only",
                "manual_save": True,
                "description": description,
                "video_url": video_url
            })
            return {"success": True, "save_mode": "link_only"}

        except Exception as e:
            logger.error(f"Failed to save video item {video_id}: {e}")
            return {"success": False, "error": str(e), "save_mode": None}

    def save_video_summary(self, video_id, title, user_goal, summary, preset="youtube_ask", video_url=""):
        """Persist summary text to Firestore with embeddings."""
        if not self.db or not self.client:
            return {"success": False, "error": "Librarian unavailable"}

        try:
            embed_text = f"Summary for {title}\nGoal: {user_goal}\n{summary}"
            embedding = self._get_embedding(embed_text)
            if not embedding:
                return {"success": False, "error": "embedding generation failed"}

            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            doc_ref = self.db.collection(self.collection_name).document(f"summary_{video_id}_{timestamp}")
            doc_ref.set({
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
                "type": "video_summary",
                "embedding": Vector(embedding)
            })
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to save summary for {video_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_saved_videos(self, limit=50):
        """Retrieve saved videos with deduped entries for UI listing."""
        if not self.db: return []
        
        try:
            docs = self.db.collection(self.collection_name)\
                .where(filter=firestore.FieldFilter("type", "==", "saved_video"))\
                .order_by("indexed_at", direction=firestore.Query.DESCENDING)\
                .limit(max(limit * 8, 100))\
                .stream()

            by_video = {}
            for doc in docs:
                data = doc.to_dict()
                original_video_id = data.get('original_video_id') or data.get('video_id', '')
                if not original_video_id:
                    continue

                if original_video_id in by_video:
                    continue

                stored_video_id = data.get('video_id', '')
                video_url = data.get('video_url')
                if not video_url and original_video_id and not str(original_video_id).startswith(('saved_', 'saved_link_')):
                    video_url = f"https://youtube.com/watch?v={original_video_id}"

                by_video[original_video_id] = {
                    'video_id': original_video_id,
                    'stored_video_id': stored_video_id,
                    'title': data.get('title', 'Untitled Video'),
                    'goal': data.get('goal'),
                    'score': data.get('score'),
                    'indexed_at': data.get('indexed_at'),
                    'save_mode': data.get('save_mode', 'transcript'),
                    'description': data.get('description', ''),
                    'video_url': video_url,
                    # Keep compatibility with existing dashboard rendering.
                    'note': data.get('description', '')
                }

                if len(by_video) >= limit:
                    break

            return list(by_video.values())
        except Exception as e:
            logger.error(f"Failed to get saved videos: {e}")
            return []

    def get_saved_summaries(self, limit=50):
        """Retrieve generated video summaries."""
        if not self.db: return []

        try:
            docs = self.db.collection(self.collection_name)\
                .where(filter=firestore.FieldFilter("type", "==", "video_summary"))\
                .order_by("indexed_at", direction=firestore.Query.DESCENDING)\
                .limit(limit)\
                .stream()

            return [doc.to_dict() for doc in docs]
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
            
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"Failed to get all highlights: {e}")
            return []

    def search_history(self, query, n_results=5, goal_filter=None):
        """Semantic search using Firestore Vector Search."""
        if not self.db or not self.client:
             return {'query': query, 'results': [], 'error': 'Librarian not initialized'}
             
        try:
            # Embed query
            query_embedding_result = self.client.models.embed_content(
                model="text-embedding-004",
                contents=query,
                config={'task_type': 'RETRIEVAL_QUERY'}
            )
            query_embedding = query_embedding_result.embeddings[0].values
            
            collection_ref = self.db.collection(self.collection_name)
            
            # Vector Search
            vector_query = collection_ref.find_nearest(
                vector_field="embedding",
                query_vector=Vector(query_embedding),
                distance_measure=DistanceMeasure.COSINE,
                limit=n_results
            )
            
            results = vector_query.get()
            
            formatted_results = []
            for doc in results:
                data = doc.to_dict()
                if goal_filter and data.get('goal') != goal_filter:
                    continue
                    
                formatted_results.append({
                    'video_id': data.get('original_video_id', data.get('video_id')),
                    'title': data.get('title'),
                    'goal': data.get('goal'),
                    'score': data.get('score'),
                    'snippet': data.get('text', '')[:200] + '...',
                    'relevance': 0.0, 
                    'chunk_index': data.get('chunk_index')
                })
                
            logger.info(f"Search for '{query}' returned {len(formatted_results)} results")
            return {
                'query': query,
                'results': formatted_results
            }
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return {'query': query, 'results': [], 'error': str(e)}

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

    def chat(self, query):
        """RAG Chat Implementation using LangGraph."""
        if not self.client:
             return {"answer": "Missing Google API Key.", "sources": []}
             
        try:
            # Delegate to LangGraph Workflow
            graph = LibrarianGraph(self)
            result = graph.invoke(query)

            # Deduplicate sources
            if 'sources' in result:
                unique_sources = {s['title']: s for s in result['sources'] if 'title' in s}
                result['sources'] = list(unique_sources.values())

            return result
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {"answer": "Error processing chat via LangGraph.", "sources": []}

    def _chunk_transcript(self, transcript, chunk_size=500):
        return [transcript[i:i+chunk_size] for i in range(0, len(transcript), chunk_size)]

# Singleton
_librarian_instance = None
def get_librarian_agent():
    global _librarian_instance
    if _librarian_instance is None:
        _librarian_instance = LibrarianAgent()
    return _librarian_instance
