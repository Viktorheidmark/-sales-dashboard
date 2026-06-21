"""
Database session factory for the MCP server.

Reads DATABASE_URL from the project root .env file.
Deliberately does not import from backend/app/ to keep the dependency
direction clear: mcp_server/ may import backend models, but backend/ never
imports from mcp_server/.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load root .env (two levels up from this file: mcp_server/ → project root)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# Make backend/ importable so we can reuse the existing SQLAlchemy models
_backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(_backend_path) not in sys.path:
    sys.path.insert(0, str(_backend_path))

DATABASE_URL = os.environ["DATABASE_URL"]

_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_session():
    """Return a new SQLAlchemy session. Caller is responsible for closing it."""
    return SessionLocal()
