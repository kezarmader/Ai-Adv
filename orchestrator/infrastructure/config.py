import os

class Config:
    """Application configuration"""
    
    # Service URLs
    LLM_SERVICE_URL: str = os.getenv("LLM_SERVICE_URL", "http://llm-service:11434")
    IMAGE_SERVICE_URL: str = os.getenv("IMAGE_SERVICE_URL", "http://image-generator:5001")
    VIDEO_SERVICE_URL: str = os.getenv("VIDEO_SERVICE_URL", "http://video-generator:5003")
    POST_SERVICE_URL: str = os.getenv("POST_SERVICE_URL", "http://poster-service:5002")
    
    # LLM Configuration
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    SERVICE_NAME: str = os.getenv("SERVICE_NAME", "orchestrator")
    
    # Application Settings
    APP_TITLE: str = "AI Advertisement Generator - Orchestrator"
    APP_VERSION: str = "1.0.0"
    DEFAULT_HOST: str = os.getenv("DEFAULT_HOST", "localhost:8000")

# Global config instance
config = Config()
