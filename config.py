"""
FraudGuard – System Configuration
=================================
Manages application environments, database URIs, security keys,
session policies, and external exchange rate provider configurations.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "fraudguard-enterprise-super-secret-key-2026")
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # Valid for session
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1")

    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Paths
    MODEL_PATH = os.path.join(BASE_DIR, "model", "fraud_model.pkl")
    METRICS_PATH = os.path.join(BASE_DIR, "model", "model_metadata.json")
    DATA_PATH = os.path.join(BASE_DIR, "data", "transactions_dataset.csv")

    # Currency Service Configuration
    EXCHANGE_RATE_API_URL = os.environ.get(
        "EXCHANGE_RATE_API_URL",
        "https://open.er-api.com/v6/latest/USD"
    )
    EXCHANGE_RATE_CACHE_HOURS = int(os.environ.get("EXCHANGE_RATE_CACHE_HOURS", "2"))

class DevelopmentConfig(Config):
    DEBUG = True
    DB_PATH = os.path.join(BASE_DIR, "database", "database.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    # Production PostgreSQL or configured database
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'database', 'database.db')}")

config_dict = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}

