# database.py
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import NullPool

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL")

# fallback to local sqlite if DATABASE_URL not set
if not DATABASE_URL:
    sqlite_path = os.getenv("SQLITE_PATH", "financial_app.db")
    DATABASE_URL = f"sqlite:///{sqlite_path}"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
else:
    # SQLAlchemy prefers "postgresql://" scheme
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )

# Ensure sqlite foreign keys if using sqlite
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
