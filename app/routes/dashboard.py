"""
Dashboard Routes
================
Job Monitoring Dashboard endpoints: overall counts, processing
times and live queue statistics.
"""

import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.job_service import get_dashboard_stats, get_dead_letter_jobs
from app.queue.queue_manager import queue_manager
from app.schemas.job import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db)):
    stats = get_dashboard_stats(db)
    stats["queue"] = queue_manager.stats()
    return stats


@router.get("/queue")
def queue_stats():
    return queue_manager.stats()


@router.get("/dead-letter")
def dead_letter_jobs(db: Session = Depends(get_db)):
    """Jobs that permanently failed after exhausting all retry attempts."""
    jobs = get_dead_letter_jobs(db)
    return [
        {
            "id": j.id,
            "job_type": j.job_type.value,
            "priority": j.priority.value,
            "payload": json.loads(j.payload),
            "retries": j.retries,
            "max_retries": j.max_retries,
            "error_message": j.error_message,
            "completed_at": j.completed_at,
        }
        for j in jobs
    ]
