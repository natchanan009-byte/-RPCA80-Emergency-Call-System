"""
RPCA80 Configuration
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-this'
    DEBUG = os.environ.get('FLASK_ENV') == 'development'

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///rpca80.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'True') == 'True'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')

    # SocketIO
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.environ.get('SOCKETIO_CORS_ALLOWED_ORIGINS', '*').split(',')

    # Timezone
    TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Bangkok')

    # Demo Accounts (ต้องเปลี่ยนในการใช้งานจริง)
    DEMO_RADIO_ADMIN_USERNAME = os.environ.get('DEMO_RADIO_ADMIN_USERNAME', 'RPCA80')
    DEMO_RADIO_ADMIN_PASSWORD = os.environ.get('DEMO_RADIO_ADMIN_PASSWORD', 'RPCA6480')
    DEMO_CITIZEN_USERNAME = os.environ.get('DEMO_CITIZEN_USERNAME', 'test1234')
    DEMO_CITIZEN_PASSWORD = os.environ.get('DEMO_CITIZEN_PASSWORD', '12345678')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

# Select config based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on FLASK_ENV"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
