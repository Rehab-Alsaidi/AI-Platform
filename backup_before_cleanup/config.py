"""
Configuration management for 51Talk AI Learning Platform.
Loads environment variables and provides app configuration settings.
"""

import os
import secrets
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()


class HuggingFaceLLM:
    """
    Wrapper for Hugging Face Inference API for LLM text generation.
    """
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate_response(self, prompt: str) -> str:
        url = f"https://api-inference.huggingface.co/models/{self.model}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": 512}}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            # The response format may vary by model; handle both list and dict
            if isinstance(data, list) and "generated_text" in data[0]:
                return data[0]["generated_text"]
            elif isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"]
            elif isinstance(data, list) and "text" in data[0]:
                return data[0]["text"]
            else:
                return str(data)
        except Exception as e:
            return f"[HF API Error] {e}"

class Config:
    """Base configuration class."""
    # Flask configuration
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or os.getenv("SECRET_KEY") or secrets.token_hex(16)
    DEBUG = False
    TESTING = False
    
    # File upload settings
    UPLOAD_FOLDER = 'static/uploads'
    DOCUMENTS_DIR = os.path.join(os.getcwd(), 'documents')
    VECTOR_DB_PATH = os.path.join(os.getcwd(), 'vector_db')
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'ppt', 'pptx', 'doc', 'docx'}
    
    # Access password for the application
    ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "5151")

    # Add HuggingFace configuration
    HF_API_KEY = os.getenv("HF_API_KEY")
    HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3-8B-Instruct")
    USE_HF_API = os.getenv("USE_HF_API", "false").lower() in ("true", "1", "yes")
    
    @staticmethod
    def validate_config():
        """Validate critical configuration."""
        if Config.USE_HF_API and not Config.HF_API_KEY:
            raise ValueError("HF_API_KEY is required when USE_HF_API is enabled")

    
    # Mail configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')
    
    # Database configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'fiftyone_learning')
    DB_USER = os.getenv('DB_USER', 'admin')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'admin123')
    
    # Create required directories
    @staticmethod
    def init_app(app):
        """Initialize application configuration."""
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.DOCUMENTS_DIR, exist_ok=True)
        os.makedirs(Config.VECTOR_DB_PATH, exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    # Use a separate test database
    DB_NAME = os.getenv('TEST_DB_NAME', 'fiftyone_testing')

class ProductionConfig(Config):
    """Production configuration."""
    # Production-specific settings can be added here
    pass

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'railway': RailwayConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Return the appropriate config class based on environment variables."""
    if RAILWAY_ENV:
        return RailwayConfig
    flask_env = os.getenv('FLASK_ENV', '').lower()
    if flask_env == 'production':
        return ProductionConfig
    if flask_env == 'testing':
        return TestingConfig
    return DevelopmentConfig