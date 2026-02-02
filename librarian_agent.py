import logging
import os
from datetime import datetime
from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from config import Config

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
                    'video_id': data.get('video_id'),
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
        """RAG Chat Implementation."""
        if not self.client:
             return {"answer": "Missing Google API Key.", "sources": []}
             
        search_res = self.search_history(query, n_results=5)
        context_docs = search_res.get('results', [])
        
        if not context_docs:
            return {"answer": "I couldn't find relevant info in your library.", "sources": []}
            
        context_str = "\n\n".join([f"Source (Video: {d['title']}): {d['snippet']}" for d in context_docs])
        sources = [{"title": d['title'], "video_id": d['video_id']} for d in context_docs]
        
        prompt = f"""You are the TubeFocus Librarian.
        User Query: {query}
        Context:
        {context_str}
        Answer based on context:"""
        
        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt
            )
            return {"answer": response.text, "sources": sources}
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return {"answer": "Error processing chat.", "sources": sources}

    def _chunk_transcript(self, transcript, chunk_size=500):
        return [transcript[i:i+chunk_size] for i in range(0, len(transcript), chunk_size)]

# Singleton
_librarian_instance = None
def get_librarian_agent():
    global _librarian_instance
    if _librarian_instance is None:
        _librarian_instance = LibrarianAgent()
    return _librarian_instance
