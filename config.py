import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Load .env if present (local dev only — Render injects env vars directly)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    DEBUG = False
    SCENARIOS_DIR = Path(os.environ.get("SCENARIOS_DIR", str(BASE_DIR / "scenarios")))
    DATA_DIR = BASE_DIR / "data"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    # Fail loudly if SECRET_KEY is still the default in production
    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self):
        super().__init__()
        if self.SECRET_KEY == "dev-secret-change-in-production":
            import warnings
            warnings.warn(
                "SECRET_KEY is set to the default development value in production. "
                "Set the SECRET_KEY environment variable.",
                RuntimeWarning,
                stacklevel=2,
            )


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
