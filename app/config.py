import os
from datetime import timedelta


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in {"1", "true", "yes", "on"}

def _normalize_db_url(url: str | None) -> str | None:
    """Render/Heroku/Railway provide postgresql:// URLs which default to
    psycopg2 in SQLAlchemy. We use psycopg (v3), so rewrite the scheme."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

class BaseConfig:
    # ── Flask core ──────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-not-for-production")
    SERVER_NAME = os.getenv("SERVER_NAME") or None
    PREFERRED_URL_SCHEME = "https"

    # ── Sessions / cookies ──────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # ── SQLAlchemy ──────────────────────────────────────
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.getenv("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ── Redis / Celery ──────────────────────────────────
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "memory://")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "cache+memory://")

    # Rate limiting storage. On Render free tier (no Redis), fall back to memory.
    RATELIMIT_STORAGE_URI = os.getenv("REDIS_URL") or "memory://"
    RATELIMIT_DEFAULT = "300 per hour"
    RATELIMIT_HEADERS_ENABLED = True

    # ── CSRF ────────────────────────────────────────────
    WTF_CSRF_TIME_LIMIT = None

    # ── Uploads (used from Ph2) ─────────────────────────
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    # ── Branding ────────────────────────────────────────
    DEFAULT_UNIVERSITY_SLUG = os.getenv("DEFAULT_UNIVERSITY_SLUG", "unilorin")

    # ── Mapbox ──────────────────────────────────────────
    MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")
    POSTGIS_ENABLED = _bool("POSTGIS_ENABLED", True)

    # ── Cloudflare R2 (used from Ph4 onward) ────────────
    R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET = os.getenv("R2_BUCKET", "")
    R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL", "")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
    os.getenv("TEST_DATABASE_URL",
                "postgresql+psycopg://campusos:campusos@localhost:5432/campusos_test")
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    name = name or os.getenv("FLASK_ENV", "development")
    return _CONFIGS.get(name, DevelopmentConfig)