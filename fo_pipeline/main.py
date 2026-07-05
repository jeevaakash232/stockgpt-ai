import logging
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

# Config & Database
from config.settings import settings
from database.connection import SessionLocal
from api.routes import router as api_router

# Scheduler & Jobs
from apscheduler.schedulers.background import BackgroundScheduler
from scheduler.jobs import (
    run_morning_pipeline_job,
    run_intraday_option_chain_job,
    run_evening_analytics_job
)

# Setup logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.LOG_DIR / "pipeline.log")
    ]
)
logger = logging.getLogger("fo_pipeline")

def init_db_schema():
    """Configures database tables and applies views."""
    from database.connection import Base, engine
    import database.models
    try:
        logger.info("Creating tables using SQLAlchemy metadata...")
        Base.metadata.create_all(engine)
        logger.info("Tables created or verified.")
    except Exception as e:
        logger.error("Failed to create tables with metadata: %s", e)

    if engine.dialect.name == "postgresql":
        db = SessionLocal()
        try:
            schema_file = Path(__file__).resolve().parent / "database" / "schema.sql"
            if schema_file.exists():
                logger.info("Applying database views/indexes from schema.sql...")
                with open(schema_file, "r") as f:
                    sql = f.read()
                db.execute(text(sql))
                db.commit()
                logger.info("PostgreSQL views and indexes applied.")
            else:
                logger.warning("schema.sql file not found at %s", schema_file)
        except Exception as e:
            logger.error("Failed to apply schema migrations: %s", e)
        finally:
            db.close()

# Scheduler reference
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Handler ---
    logger.info("Bootstrapping F&O pipeline application...")
    
    # 1. Initialize database tables & views
    init_db_schema()
    
    # 2. Configure Background Scheduler Jobs
    logger.info("Starting background scheduler...")
    
    # Run morning Bhavcopy job at 8:30 AM daily
    scheduler.add_job(
        run_morning_pipeline_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8,
        minute=30,
        id="morning_bhavcopy_job"
    )
    
    # Run live option chain logging every 5 minutes from Monday to Friday (9:15 AM - 3:30 PM)
    scheduler.add_job(
        run_intraday_option_chain_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",
        minute="*/5",
        id="intraday_option_chain_job"
    )
    
    # Run evening analytics compilation at 5:30 PM daily
    scheduler.add_job(
        run_evening_analytics_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=17,
        minute=30,
        id="evening_analytics_job"
    )
    
    scheduler.start()
    logger.info("Scheduler started successfully.")
    
    yield
    
    # --- Shutdown Handler ---
    logger.info("Shutting down background scheduler...")
    scheduler.shutdown()
    logger.info("Cleanup completed successfully.")

app = FastAPI(
    title="NSE F&O Data Pipeline & Analytics API",
    description="Automated F&O Bhavcopy ingestion, live Option Chain logging, and DB-driven PCR/Max Pain calculations.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(api_router, prefix="/api")

@app.get("/")
def health_check():
    """Basic health check route."""
    return {
        "status": "healthy",
        "service": "NSE F&O Data Pipeline",
        "db_dialect": SessionLocal().bind.dialect.name
    }

if __name__ == "__main__":
    logger.info("Booting local development server on port 8001...")
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
