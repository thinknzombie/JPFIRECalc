import os
from pathlib import Path

BASE_DIR = Path(__file__).parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    DEBUG = False
    SCENARIOS_DIR = BASE_DIR / "scenarios"
    DATA_DIR = BASE_DIR / "data"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
