"""
Application entrypoint.
Starts the FastAPI server and, via the lifespan handler, launches
the background worker pool in the same asyncio event loop. Workers
run independently of any single request but share the process.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.database import Base, engine
from app.core.logger import get_logger
from app.routes import jobs, dashboard
from app.workers.worker import start_workers, stop_workers

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    await start_workers()
    logger.info("Application startup complete")
    yield
    await stop_workers()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Async Job Processing System",
    description="Submit long-running jobs and process them asynchronously with background workers.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs.router)
app.include_router(dashboard.router)

# Simple dashboard UI (static HTML/JS, polls the API above).
# Visit http://127.0.0.1:8000/dashboard-ui/
app.mount("/dashboard-ui", StaticFiles(directory="static", html=True), name="dashboard-ui")


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "Async Job Processing System"}
