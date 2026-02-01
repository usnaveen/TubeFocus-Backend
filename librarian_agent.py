import chromadb
from chromadb.config import Settings
import logging
import os
from datetime import datetime
import google.generativeai as genai
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup Gemini
if Config.GOOGLE_API_KEY:
    genai.configure(api_key=Config.GOOGLE_API_KEY)
else:
    logger.warning("GOOGLE_API_KEY not found. Librarian Chat will not function.")

class LibrarianAgent:
    """
    The Librarian Agent - Memory and Semantic Search
    
    This agent maintains long-term memory of watched videos and enables
    semantic search over viewing history using vector embeddings.
    """
    
    def __init__(self, persist_directory="./chroma_data"):
        """Initialize the Librarian with persistent vector storage."""
        try:
            # Initialize ChromaDB with persistent storage
            # Note: On Cloud Run, this path is ephemeral unless mounted to a volume.
            self.client = chromadb.PersistentClient(path=persist_directory)
            
            # Create or get collection for video transcripts
            self.collection = self.client.get_or_create_collection(
                name="video_transcripts",
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info(f"Librarian Agent initialized with {self.collection.count()} indexed videos")
            
        except Exception as e:
            logger.error(f"Failed to initialize Librarian: {str(e)}")
            # Fallback to non-persistent or disabled if needed, but let's try to fail loudly or handle it
            self.client = None
            self.collection = None
    
    def index_video(self, video_id, title, transcript, goal, score, metadata=None):
        """
        Index a video transcript for semantic search.
        
        Args:
            video_id: YouTube video ID
            title: Video title
            transcript: Full transcript text
            goal: User's goal when watching
            score: Relevance score
            metadata: Optional additional metadata
            
        Returns:
            bool: Success status
        """
        if not self.collection:
             return False

        try:
            if not transcript or len(transcript.strip()) == 0:
                logger.warning(f"Skipping indexing for {video_id}: No transcript")
                return False
            
            # Chunk transcript into ~500 char segments for better retrieval
            chunks = self._chunk_transcript(transcript, chunk_size=500)
            
            if not chunks:
                logger.warning(f"No chunks created for {video_id}")
                return False
            
            # Prepare data for insertion
            documents = []
            metadatas = []
            ids = []
            
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                
                chunk_metadata = {
                    "video_id": video_id,
                    "title": title,
                    "goal": goal,
                    "score": float(score),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "indexed_at": datetime.now().isoformat()
                }
                
                # Add custom metadata if provided
                if metadata:
                    chunk_metadata.update(metadata)
                
                metadatas.append(chunk_metadata)
                ids.append(f"{video_id}_{i}")
            
            # Add to collection (ChromaDB handles embedding automatically)
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Indexed video {video_id}: {len(chunks)} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to index video {video_id}: {str(e)}")
            return False
    
    def search_history(self, query, n_results=5, goal_filter=None):
        """
        Semantic search over watched video history.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            goal_filter: Optional filter by goal
            
        Returns:
            dict: Search results with videos and relevance
        """
        if not self.collection:
            return {'query': query, 'results': [], 'error': 'Librarian not initialized'}

        try:
            # Build where filter if goal specified
            where_filter = None
            if goal_filter:
                where_filter = {"goal": goal_filter}
            
            # Perform semantic search
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            
            # Format results
            formatted_results = []
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        'video_id': results['metadatas'][0][i]['video_id'],
                        'title': results['metadatas'][0][i]['title'],
                        'goal': results['metadatas'][0][i]['goal'],
                        'score': results['metadatas'][0][i]['score'],
                        'snippet': results['documents'][0][i][:200] + '...',
                        'relevance': 1 - results['distances'][0][i] if results.get('distances') else None,
                        'chunk_index': results['metadatas'][0][i]['chunk_index']
                    })
            
            logger.info(f"Search for '{query}' returned {len(formatted_results)} results")
            return {
                'query': query,
                'results': formatted_results,
                'total_indexed': self.collection.count()
            }
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return {
                'query': query,
                'results': [],
                'error': str(e)
            }
    
    def get_video_by_id(self, video_id):
        """Retrieve all chunks for a specific video."""
        if not self.collection: return None

        try:
            results = self.collection.get(
                where={"video_id": video_id}
            )
            
            if not results or not results['ids']:
                return None
            
            # Combine chunks
            chunks = sorted(
                zip(results['documents'], results['metadatas']),
                key=lambda x: x[1]['chunk_index']
            )
            
            full_transcript = ' '.join([chunk[0] for chunk in chunks])
            metadata = chunks[0][1]  # Metadata from first chunk
            
            return {
                'video_id': video_id,
                'title': metadata['title'],
                'goal': metadata['goal'],
                'score': metadata['score'],
                'transcript': full_transcript,
                'indexed_at': metadata['indexed_at']
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve video {video_id}: {str(e)}")
            return None
    
    def get_recent_videos(self, n=10):
        """Get most recently indexed videos."""
        if not self.collection: return []

        try:
            # Get all and sort by indexed_at
            # Note: ChromaDB doesn't support ordering, so we get more and sort
            all_results = self.collection.get(limit=100)
            
            if not all_results or not all_results['ids']:
                return []
            
            # Group by video_id
            videos = {}
            for i, vid_id in enumerate(all_results['ids']):
                video_id = all_results['metadatas'][i]['video_id']
                if video_id not in videos:
                    videos[video_id] = all_results['metadatas'][i]
            
            # Sort by indexed_at
            sorted_videos = sorted(
                videos.values(),
                key=lambda x: x.get('indexed_at', ''),
                reverse=True
            )
            
            return sorted_videos[:n]
            
        except Exception as e:
            logger.error(f"Failed to get recent videos: {str(e)}")
            return []
    
    def get_stats(self):
        """Get Librarian statistics."""
        if not self.collection: return {'error': 'Not initialized'}

        try:
            count = self.collection.count()
            
            # Get unique video count
            all_results = self.collection.get()
            unique_videos = set()
            if all_results and all_results['metadatas']:
                for metadata in all_results['metadatas']:
                    unique_videos.add(metadata['video_id'])
            
            return {
                'total_chunks': count,
                'unique_videos': len(unique_videos),
                'collection_name': self.collection.name
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {
                'total_chunks': 0,
                'unique_videos': 0,
                'error': str(e)
            }
    
    def delete_video(self, video_id):
        """Delete all chunks for a video."""
        if not self.collection: return False

        try:
            # Get all IDs for this video
            results = self.collection.get(
                where={"video_id": video_id}
            )
            
            if results and results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Deleted video {video_id}: {len(results['ids'])} chunks")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete video {video_id}: {str(e)}")
            return False
    
        return chunks
        
    def get_all_highlights(self):
        """
        Retrieve all stored highlights (marked with type='highlight' metadata).
        """
        if not self.collection: return []
        
        try:
            # Query based on metadata filter
            results = self.collection.get(
                where={"type": "highlight"}
            )
            
            highlights = []
            if results and results['ids']:
                for i in range(len(results['ids'])):
                    meta = results['metadatas'][i]
                    # Format for frontend
                    highlights.append({
                        'id': results['ids'][i],
                        'video_id': meta.get('original_video_id') or meta.get('video_id'),
                        'text': results['documents'][i],
                        'note': meta.get('note', ''),
                        'timestamp': meta.get('timestamp', 0),
                        'video_url': meta.get('video_url', ''),
                        'created_at': meta.get('indexed_at', '')
                    })
                    
            # Sort by creation date (newest first)
            highlights.sort(key=lambda x: x['created_at'], reverse=True)
            return highlights
            
        except Exception as e:
            logger.error(f"Failed to get highlights: {str(e)}")
            return []

    def chat(self, query):
        """
        RAG Chat: Answer query using library context.
        """
        if not Config.GOOGLE_API_KEY:
            return {"answer": "I can't chat right now because the Google API Key is missing.", "sources": []}
            
        # 1. Retrieve Context
        search_res = self.search_history(query, n_results=5)
        context_docs = search_res.get('results', [])
        
        if not context_docs:
            return {"answer": "I couldn't find any relevant information in your library.", "sources": []}
            
        # Format context for prompt
        context_str = ""
        sources = []
        for i, doc in enumerate(context_docs):
            context_str += f"Source {i+1} (Video: {doc['title']}):\n{doc['snippet']}\n\n"
            sources.append({
                "title": doc['title'],
                "video_id": doc['video_id'],
                "score": doc['relevance']
            })
            
        # 2. Generate Answer
        prompt = f"""You are the TubeFocus Librarian, a helpful assistant with access to the user's video library.
        
        User Query: {query}
        
        Use the following information retrieved from the user's library to answer the query. 
        If the answer is not in the context, say you don't know based on their library.
        Keep the answer concise and helpful.
        
        Context:
        {context_str}
        
        Answer:"""
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            response = model.generate_content(prompt)
            return {
                "answer": response.text,
                "sources": sources
            }
        except Exception as e:
            logger.error(f"Chat generation failed: {e}")
            return {
                "answer": "Sorry, I encountered an error generating the response.",
                "sources": sources # Return sources even if generation fails
            }

# Global instance (singleton pattern for agent)
_librarian_instance = None

def get_librarian_agent():
    """Get or create the global Librarian Agent instance."""
    global _librarian_instance
    if _librarian_instance is None:
        _librarian_instance = LibrarianAgent()
    return _librarian_instance
