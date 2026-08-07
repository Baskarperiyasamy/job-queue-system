"""
Job Service
===========
All business logic for creating and reading jobs lives here, so
routes stay thin and the worker layer can reuse the same functions.
"""

import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.core.logger import get_logger, log_event
from app.models.job import Job, JobStatus, JobPriority
from app.schemas.job import JobCreate

logger = get_logger("job_service")


def create_job(db: Session, job_data: JobCreate) -> Job:
    job = Job(
        job_type=job_data.job_type,
        payload=json.dumps(job_data.payload),
        priority=job_data.priority,
        status=JobStatus.PENDING,
        max_retries=job_data.max_retries
        if job_data.max_retries is not None
        else settings.DEFAULT_MAX_RETRIES,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    log_event(
        logger,
        "Job submitted",
        job_id=job.id,
        job_type=job.job_type.value,
        priority=job.priority.value,
    )
    return job


def get_job(db: Session, job_id: str) -> Optional[Job]:
    return db.query(Job).filter(Job.id == job_id).first()


def list_jobs(
    db: Session,
    status: Optional[JobStatus] = None,
    job_type: Optional[str] = None,
    priority: Optional[JobPriority] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    if job_type:
        query = query.filter(Job.job_type == job_type)
    if priority:
        query = query.filter(Job.priority == priority)
    return (
        query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()
    )


def cancel_job(db: Session, job_id: str) -> Optional[Job]:
    """Cancel a job. Only jobs still PENDING can be cancelled — once a
    worker has picked it up (RUNNING) it's too late to safely stop it."""
    job = get_job(db, job_id)
    if job is None:
        return None
    if job.status != JobStatus.PENDING:
        return job  # caller checks status and reports the conflict

    job.status = JobStatus.CANCELLED
    job.completed_at = func.now()
    db.commit()
    db.refresh(job)

    log_event(logger, "Job cancelled", job_id=job.id)
    return job


def get_dead_letter_jobs(db: Session, limit: int = 50, offset: int = 0):
    return (
        db.query(Job)
        .filter(Job.is_dead_letter == 1)
        .order_by(Job.completed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_pending_jobs_ordered(db: Session):
    """Used on startup to re-load any jobs left pending from a previous run."""
    return db.query(Job).filter(Job.status == JobStatus.PENDING).order_by(
        Job.created_at.asc()
    ).all()


def get_dashboard_stats(db: Session) -> dict:
    total = db.query(func.count(Job.id)).scalar() or 0
    pending = db.query(func.count(Job.id)).filter(Job.status == JobStatus.PENDING).scalar() or 0
    running = db.query(func.count(Job.id)).filter(Job.status == JobStatus.RUNNING).scalar() or 0
    completed = db.query(func.count(Job.id)).filter(Job.status == JobStatus.COMPLETED).scalar() or 0
    failed = db.query(func.count(Job.id)).filter(Job.status == JobStatus.FAILED).scalar() or 0
    cancelled = db.query(func.count(Job.id)).filter(Job.status == JobStatus.CANCELLED).scalar() or 0
    dead_letter = db.query(func.count(Job.id)).filter(Job.is_dead_letter == 1).scalar() or 0

    avg_time = db.query(func.avg(Job.processing_time_seconds)).filter(
        Job.status == JobStatus.COMPLETED
    ).scalar()

    finished = completed + failed
    success_rate = (completed / finished * 100) if finished > 0 else None

    return {
        "total_jobs": total,
        "pending": pending,
        "running": running,
        "completed": completed,
        "failed": failed,
        "cancelled": cancelled,
        "dead_letter": dead_letter,
        "average_processing_time_seconds": round(avg_time, 3) if avg_time else None,
        "success_rate_percent": round(success_rate, 2) if success_rate is not None else None,
    }
