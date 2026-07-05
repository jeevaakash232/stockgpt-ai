import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import settings

logger = logging.getLogger(__name__)

# Base class for SQLAlchemy ORM models
Base = declarative_base()

# Configure engine with robust pooling parameters
try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=5,  # short timeout for quick failover
        pool_recycle=1800,  # recycle connections after 30 minutes
        echo=False
    )
    # Test connection
    with engine.connect() as conn:
        pass
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("SQLAlchemy Database engine connected successfully to PostgreSQL.")
except Exception as e:
    logger.warning("PostgreSQL connection failed: %s. Falling back to local SQLite database 'fo_pipeline.db'.", e)
    engine = create_engine(
        "sqlite:///fo_pipeline.db",
        pool_recycle=1800,
        echo=False
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Context manager generator for DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
