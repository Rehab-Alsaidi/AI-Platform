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


class OpenRouterLLM:
    """
    Wrapper for OpenRouter API for LLM text generation using GPT and other models.
    """
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def generate_response(self, prompt: str) -> str:
        """Generate response using OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://51talk-ai-learning.com",  # Replace with your actual domain
            "X-Title": "51Talk AI Learning Platform"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 800,
            "temperature": 0.7,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0
        }
        
        try:
            response = requests.post(
                self.base_url, headers=headers, json=payload, timeout=60
            )
            
            if response.status_code == 429:
                return "[Rate Limited] Too many requests. Please wait a moment and try again."
            elif response.status_code == 401:
                return "[Authentication Error] Invalid API key."
            elif response.status_code == 402:
                return "[Insufficient Credits] Please check your OpenRouter account balance."
            elif response.status_code != 200:
                return f"[API Error] Service unavailable (Status: {response.status_code})"
                
            data = response.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                return "[Error] No response generated"
                
        except requests.exceptions.Timeout:
            return "[Timeout] Request timed out. Please try again."
        except requests.exceptions.ConnectionError:
            return "[Connection Error] Unable to connect to OpenRouter service."
        except Exception as e:
            return f"[Error] {str(e)}"


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

    # OpenRouter configuration
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    
    @staticmethod
    def validate_config():
        """Validate critical configuration."""
        if not Config.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required")
    
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
    DATABASE_URL = os.getenv("DATABASE_URL")

    @staticmethod
    def get_db_uri():
        """Return full SQLAlchemy URI from DATABASE_URL or fallback values."""
        if Config.DATABASE_URL:
            # Replace 'postgres://' with 'postgresql://' if needed
            return Config.DATABASE_URL.replace('postgres://', 'postgresql://')
        return f"postgresql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
    
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
    DB_NAME = os.getenv('TEST_DB_NAME', 'fiftyone_testing')

class ProductionConfig(Config):
    """Production configuration."""
    pass

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Return the appropriate config class based on environment variables."""
    flask_env = os.getenv('FLASK_ENV', '').lower()
    if flask_env == 'production':
        return ProductionConfig
    if flask_env == 'testing':
        return TestingConfig
    return DevelopmentConfig
