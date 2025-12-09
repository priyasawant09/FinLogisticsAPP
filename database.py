# database.py
# Minimal, robust DB setup: supports DATABASE_URL (Postgres) or local SQLite fallback.
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.pool import NullPool

# ------------------ Configuration ------------------
DATABASE_URL = os.getenv("DATABASE_URL")  # prefer env var (Render Postgres)
SQLITE_FALLBACK_PATH = os.getenv("SQLITE_PATH", "financial_app.db")

# ------------------ Engine selection ------------------
if not DATABASE_URL:
    # Use file-based SQLite locally
    url = f"sqlite:///{SQLITE_FALLBACK_PATH}"
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,  # avoid connection pooling issues with SQLite file
    )
else:
    # Normalize scheme for SQLAlchemy (older libs expect postgresql://)
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # helps with dropped connections
        future=True,
    )

# ------------------ SQLite PRAGMA ------------------
# Ensure foreign keys are enabled on SQLite connections
if "sqlite" in str(engine.url):
    @event.listens_for(engine, "connect")
    def _sqlite_enable_foreign_keys(dbapi_conn, conn_record):
        try:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception:
            # pragma may fail for non-sqlite DB-API; ignore safely
            pass

# ------------------ Session / Base ------------------
# Use scoped_session for thread/process safety in web servers
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()

# generator dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

