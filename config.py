"""Application configuration, read from environment variables.

Secrets are never hardcoded here: they come from the .env file
(or from the environment that Docker Compose provides).
"""
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Loads variables from a local .env file if one exists.
# Inside Docker, Compose injects the variables, so this does nothing harmful.
load_dotenv()


def build_database_uri() -> str:
    """Build the SQLAlchemy connection string for PostgreSQL."""
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return explicit_url

    user = quote_plus(os.getenv("POSTGRES_USER", "taskflow_user"))
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    name = os.getenv("POSTGRES_DB", "taskflow")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    APP_USER_NAME = os.getenv("APP_USER_NAME", "Student")


class TestConfig:
    """Isolated settings for pytest. Never points at development data."""

    TESTING = True
    SECRET_KEY = "test-only-secret"
    # In-memory SQLite by default; CI overrides this with a PostgreSQL URL.
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_USER_NAME = "Tester"
