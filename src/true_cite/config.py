from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache
import os

class Settings(BaseSettings):
    # --- API Keys and Secrets ---
    GOOGLE_API_KEY: str = Field(..., description="Vertex AI API Key")
    
    # --- RAG Parameters ---
    
    EMBEDDING_MODEL: str = "text-embedding-004"
    LLM_MODEL: str = "gemini-1.5-pro"
    CHROMA_COLLECTION: str = "audit_policies"
    
    # --- Vector Search Tuning ---
    CHUNK_SIZE: int = 400
    PARENT_CHUNK_SIZE: int = 2000
    SEARCH_TOP_K: int = 5
    RERANK_THRESHOLD: float = 0.5

    # --- App Info ---
    APP_NAME: str = "TrueCite"
    DEBUG: bool = False

    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()