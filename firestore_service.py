"""
Firestore Service for TubeFocus
Provides persistent storage for highlights, user data, and video metadata.
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firebase initialization
_firestore_client = None
_initialized = False

def initialize_firestore():
    """Initialize Firestore client."""
    global _firestore_client, _initialized
    
    if _initialized:
        return _firestore_client
    
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # Check if already initialized
        try:
            firebase_admin.get_app()
        except ValueError:
            # Not initialized, so initialize
            # On Cloud Run, use Application Default Credentials
            if os.environ.get('GOOGLE_CLOUD_PROJECT') or os.environ.get('K_SERVICE'):
                # Running on Google Cloud - use default credentials
                firebase_admin.initialize_app()
                logger.info("Firestore initialized with default credentials (Cloud Run)")
            else:
                # Local development - check for service account
                cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
                if cred_path and os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    logger.info(f"Firestore initialized with service account: {cred_path}")
                else:
                    # Try default credentials anyway
                    firebase_admin.initialize_app()
                    logger.info("Firestore initialized with default credentials (local)")
        
        _firestore_client = firestore.client()
        _initialized = True
        logger.info("Firestore client ready")
        return _firestore_client
        
    except Exception as e:
        logger.error(f"Failed to initialize Firestore: {str(e)}")
        _initialized = False
        return None


def get_firestore():
    """Get or create Firestore client."""
    global _firestore_client
    if _firestore_client is None:
        initialize_firestore()
    return _firestore_client


# ===== HIGHLIGHTS COLLECTION =====

def save_highlight(highlight: Dict) -> Optional[str]:
    """
    Save a highlight to Firestore.
    
    Args:
        highlight: {
            video_id: str,
            video_title: str,
            timestamp: int,
            timestamp_formatted: str,
            note: str (optional),
            transcript: str (optional),
            video_url: str,
            user_id: str (optional, for future auth),
            goal: str (optional)
        }
    
    Returns:
        Document ID if successful, None otherwise
    """
    db = get_firestore()
    if not db:
        logger.warning("Firestore not available, highlight not saved to cloud")
        return None
    
    try:
        # Ensure required fields
        if not highlight.get('video_id') or highlight.get('timestamp') is None:
            raise ValueError("video_id and timestamp are required")
        
        # Add metadata
        highlight_doc = {
            **highlight,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'synced': True
        }
        
        # Create document ID from video_id and timestamp
        doc_id = f"{highlight['video_id']}_{highlight['timestamp']}"
        
        # Save to Firestore
        db.collection('highlights').document(doc_id).set(highlight_doc, merge=True)
        
        logger.info(f"Highlight saved: {doc_id}")
        return doc_id
        
    except Exception as e:
        logger.error(f"Failed to save highlight: {str(e)}")
        return None


def get_highlights(user_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """
    Get all highlights, optionally filtered by user.
    
    Args:
        user_id: Optional user ID to filter by
        limit: Maximum number of results
    
    Returns:
        List of highlight documents
    """
    db = get_firestore()
    if not db:
        return []
    
    try:
        query = db.collection('highlights')
        
        if user_id:
            query = query.where('user_id', '==', user_id)
        
        query = query.order_by('created_at', direction='DESCENDING').limit(limit)
        
        docs = query.stream()
        return [{'id': doc.id, **doc.to_dict()} for doc in docs]
        
    except Exception as e:
        logger.error(f"Failed to get highlights: {str(e)}")
        return []


def get_highlights_for_video(video_id: str) -> List[Dict]:
    """Get all highlights for a specific video."""
    db = get_firestore()
    if not db:
        return []
    
    try:
        docs = db.collection('highlights') \
            .where('video_id', '==', video_id) \
            .order_by('timestamp') \
            .stream()
        
        return [{'id': doc.id, **doc.to_dict()} for doc in docs]
        
    except Exception as e:
        logger.error(f"Failed to get highlights for video {video_id}: {str(e)}")
        return []


def delete_highlight(doc_id: str) -> bool:
    """Delete a highlight by document ID."""
    db = get_firestore()
    if not db:
        return False
    
    try:
        db.collection('highlights').document(doc_id).delete()
        logger.info(f"Highlight deleted: {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete highlight {doc_id}: {str(e)}")
        return False


# ===== VIDEO METADATA COLLECTION =====

def save_video_metadata(video_id: str, metadata: Dict) -> bool:
    """Save video metadata to Firestore."""
    db = get_firestore()
    if not db:
        return False
    
    try:
        doc = {
            **metadata,
            'video_id': video_id,
            'updated_at': datetime.now().isoformat()
        }
        
        db.collection('videos').document(video_id).set(doc, merge=True)
        return True
        
    except Exception as e:
        logger.error(f"Failed to save video metadata: {str(e)}")
        return False


def get_video_metadata(video_id: str) -> Optional[Dict]:
    """Get video metadata from Firestore."""
    db = get_firestore()
    if not db:
        return None
    
    try:
        doc = db.collection('videos').document(video_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
        
    except Exception as e:
        logger.error(f"Failed to get video metadata: {str(e)}")
        return None


# ===== SESSION DATA COLLECTION =====

def save_session(session_id: str, session_data: Dict) -> bool:
    """Save session data to Firestore."""
    db = get_firestore()
    if not db:
        return False
    
    try:
        doc = {
            **session_data,
            'session_id': session_id,
            'updated_at': datetime.now().isoformat()
        }
        
        db.collection('sessions').document(session_id).set(doc, merge=True)
        return True
        
    except Exception as e:
        logger.error(f"Failed to save session: {str(e)}")
        return False


def get_session(session_id: str) -> Optional[Dict]:
    """Get session data from Firestore."""
    db = get_firestore()
    if not db:
        return None
    
    try:
        doc = db.collection('sessions').document(session_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
        
    except Exception as e:
        logger.error(f"Failed to get session: {str(e)}")
        return None


def get_recent_sessions(limit: int = 20) -> List[Dict]:
    """Get recent sessions."""
    db = get_firestore()
    if not db:
        return []
    
    try:
        docs = db.collection('sessions') \
            .order_by('updated_at', direction='DESCENDING') \
            .limit(limit) \
            .stream()
        
        return [{'id': doc.id, **doc.to_dict()} for doc in docs]
        
    except Exception as e:
        logger.error(f"Failed to get recent sessions: {str(e)}")
        return []


# ===== CHROMADB BACKUP TO GCS =====

def backup_chromadb_to_gcs(local_path: str = './chroma_data', bucket_name: Optional[str] = None) -> bool:
    """
    Backup ChromaDB data to Google Cloud Storage.
    
    Args:
        local_path: Path to local ChromaDB data directory
        bucket_name: GCS bucket name (defaults to project's default bucket)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from google.cloud import storage
        import shutil
        import tempfile
        
        # Create storage client
        client = storage.Client()
        
        # Use default bucket if not specified
        if not bucket_name:
            project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'tubefocus')
            bucket_name = f"{project_id}-chromadb-backup"
        
        # Get or create bucket
        try:
            bucket = client.get_bucket(bucket_name)
        except Exception:
            bucket = client.create_bucket(bucket_name, location='us-central1')
            logger.info(f"Created bucket: {bucket_name}")
        
        # Create timestamped backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"chromadb_backup_{timestamp}.tar.gz"
        
        # Create tar archive
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
            shutil.make_archive(
                tmp.name.replace('.tar.gz', ''),
                'gztar',
                root_dir=os.path.dirname(local_path),
                base_dir=os.path.basename(local_path)
            )
            
            # Upload to GCS
            blob = bucket.blob(backup_name)
            blob.upload_from_filename(tmp.name)
            
            # Also update 'latest' pointer
            latest_blob = bucket.blob('chromadb_latest.tar.gz')
            latest_blob.upload_from_filename(tmp.name)
        
        logger.info(f"ChromaDB backed up to gs://{bucket_name}/{backup_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to backup ChromaDB: {str(e)}")
        return False


def restore_chromadb_from_gcs(local_path: str = './chroma_data', bucket_name: Optional[str] = None) -> bool:
    """
    Restore ChromaDB data from Google Cloud Storage.
    
    Args:
        local_path: Path to restore ChromaDB data to
        bucket_name: GCS bucket name
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from google.cloud import storage
        import shutil
        import tempfile
        import tarfile
        
        # Create storage client
        client = storage.Client()
        
        # Use default bucket if not specified
        if not bucket_name:
            project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'tubefocus')
            bucket_name = f"{project_id}-chromadb-backup"
        
        # Get bucket
        try:
            bucket = client.get_bucket(bucket_name)
        except Exception:
            logger.warning(f"Bucket {bucket_name} not found, no backup to restore")
            return False
        
        # Download latest backup
        blob = bucket.blob('chromadb_latest.tar.gz')
        if not blob.exists():
            logger.warning("No ChromaDB backup found")
            return False
        
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            
            # Extract to local path
            with tarfile.open(tmp.name, 'r:gz') as tar:
                # Remove existing data
                if os.path.exists(local_path):
                    shutil.rmtree(local_path)
                
                # Extract
                tar.extractall(path=os.path.dirname(local_path))
        
        logger.info(f"ChromaDB restored from gs://{bucket_name}/chromadb_latest.tar.gz")
        return True
        
    except Exception as e:
        logger.error(f"Failed to restore ChromaDB: {str(e)}")
        return False


# ===== INITIALIZATION =====

# Try to initialize on import
try:
    initialize_firestore()
except Exception as e:
    logger.warning(f"Firestore not available at startup: {str(e)}")
