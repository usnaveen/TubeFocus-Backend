import json
import os
import logging
from dotenv import load_dotenv

# Load .env file in development (will be ignored in production)
load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    """Centralized configuration management for TubeFocus Backend"""
    
    # ===== API Keys =====
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    API_KEY = os.environ.get('API_KEY', 'changeme')
    
    # ===== Application Settings =====
    MIN_FEEDBACK = int(os.environ.get('MIN_FEEDBACK', '5'))
    PORT = int(os.environ.get('PORT', '8080'))
    
    # ===== Environment =====
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

    # ===== Rate Limiting =====
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200 per day;50 per hour')
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    
    # ===== Redis Configuration - Removed (Not needed) =====
    # Redis integration removed in favor of simplified architecture
    REDIS_HOST = None
    REDIS_PORT = None
    REDIS_DB = None
    REDIS_PASSWORD = None
    REDIS_USERNAME = None
    CACHE_TTL_SECONDS = 0
    
    # ===== Model Weights =====
    DEFAULT_WEIGHTS = {
        "description": 0.25,
        "title": 0.25,
        "tags": 0.25,
        "category": 0.25
    }
    WEIGHTS_FILE = "weights.json"
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        warnings = []
        
        # Critical validations
        if not cls.YOUTUBE_API_KEY:
            errors.append("YOUTUBE_API_KEY is not set")
        
        if not cls.GOOGLE_API_KEY:
            errors.append("GOOGLE_API_KEY is not set")
        
        # Warnings for default values
        if cls.API_KEY == 'changeme':
            warnings.append("API_KEY is using default value 'changeme' - should be changed in production")
        
        if cls.ENVIRONMENT == 'production' and cls.DEBUG:
            warnings.append("DEBUG is enabled in production environment")
        
        # Log warnings
        if warnings:
            for warning in warnings:
                logger.warning(f"Configuration warning: {warning}")
        
        # Raise errors if any
        if errors:
            error_msg = "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        logger.info(f"Configuration validated successfully (Environment: {cls.ENVIRONMENT})")
        return True
    
    @classmethod
    def get_info(cls):
        """Get safe configuration info (without sensitive data)"""
        return {
            'environment': cls.ENVIRONMENT,
            'debug': cls.DEBUG,
            'port': cls.PORT,
            'min_feedback': cls.MIN_FEEDBACK,
            'youtube_api_configured': bool(cls.YOUTUBE_API_KEY),
            'google_api_configured': bool(cls.GOOGLE_API_KEY),
            'redis_configured': bool(cls.REDIS_HOST and cls.REDIS_PASSWORD),
        }

# Legacy support - keep these for backwards compatibility
DEFAULT_WEIGHTS = Config.DEFAULT_WEIGHTS
WEIGHTS_FILE = Config.WEIGHTS_FILE
REDIS_HOST = Config.REDIS_HOST
REDIS_PORT = Config.REDIS_PORT
REDIS_DB = Config.REDIS_DB
REDIS_PASSWORD = Config.REDIS_PASSWORD
REDIS_USERNAME = Config.REDIS_USERNAME
CACHE_TTL_SECONDS = Config.CACHE_TTL_SECONDS

def load_weights():
    """Load model weights from file"""
    if os.path.exists(WEIGHTS_FILE):
        with open(WEIGHTS_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_WEIGHTS.copy()

def save_weights(weights):
    """Save model weights to file"""
    with open(WEIGHTS_FILE, 'w') as f:
        json.dump(weights, f, indent=2)

# Validate configuration on import (can be disabled if needed)
if os.environ.get('SKIP_CONFIG_VALIDATION', '').lower() != 'true':
    try:
        Config.validate()
    except RuntimeError as e:
        logger.warning(f"Configuration validation failed: {e}")
        logger.warning("Set SKIP_CONFIG_VALIDATION=true to skip validation")