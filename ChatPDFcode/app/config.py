"""
Configuration settings for ChatPDF Backend
Uses pydantic-settings for environment variable management
"""

from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # ======================
    # API Keys
    # ======================
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    
    # ======================
    # Redis Configuration
    # ======================
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # ======================
    # Qdrant Configuration
    # ======================
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    
    # ======================
    # File Upload Settings
    # ======================
    MAX_FILE_SIZE_MB: int = 50
    MAX_FILES_PER_SESSION: int = 20
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]
    
    # ======================
    # Session Settings
    # ======================
    SESSION_EXPIRY_HOURS: int = 2
    SESSION_CLEANUP_INTERVAL_MINUTES: int = 30
    
    # ======================
    # Embedding Model
    # ======================
    EMBEDDING_MODEL: str = "sentence-transformers/multilingual-e5-large"
    EMBEDDING_DIMENSION: int = 1024
    
    # ======================
    # Chunking Settings
    # ======================
    CHUNK_SIZE: int = 1000  # tokens
    CHUNK_OVERLAP: int = 200  # tokens
    
    # ======================
    # RAG Settings
    # ======================
    TOP_K_RETRIEVAL: int = 20
    TOP_K_FINAL: int = 10
    RRF_K: int = 60  # Reciprocal Rank Fusion constant
    
    # ======================
    # LLM Settings
    # ======================
    LLM_MODEL: str = "gpt-4-turbo-preview"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1
    LLM_CONTEXT_WINDOW: int = 100000  # Reserve tokens for context
    
    # ======================
    # Vision Model
    # ======================
    VISION_MODEL: str = "gpt-4-vision-preview"
    
    # ======================
    # CORS Settings
    # ======================
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]
    
    # ======================
    # Debug & Logging
    # ======================
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
