"""
Job Routes
==========
Job Submission API (create) + endpoints to check job status/results.
"""

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limiter import enforce_rate_limit
from app.models.job import JobStatus, JobPriority, JobType
from app.schemas.job import JobCreate, JobResponse
from app.services import job_service
from app.queue.queue_manager import queue_manager

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def _to_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        payload=json.loads(job.payload),
        priority=job.priority,
        status=job.status,
        retries=job.retries,
        max_retries=job.max_retries,
        result=job.result,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        processing_time_seconds=job.processing_time_seconds,
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
async def submit_job(job_data: JobCreate, db: Session = Depends(get_db)):
    """Create a new job and place it on the processing queue.
    Rate limited to protect against accidental submission floods."""
    job = job_service.create_job(db, job_data)
    await queue_manager.enqueue(job.id, job.priority)
    return _to_response(job)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    status: Optional[JobStatus] = None,
    job_type: Optional[JobType] = None,
    priority: Optional[JobPriority] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    jobs = job_service.list_jobs(db, status, job_type, priority, limit, offset)
    return [_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


@router.delete("/{job_id}", response_model=JobResponse)
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a job. Only works while the job is still PENDING — once a
    worker has started running it, it can no longer be safely cancelled."""
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel a job with status '{job.status.value}'. "
                   f"Only pending jobs can be cancelled.",
        )
    job = job_service.cancel_job(db, job_id)
    return _to_response(job)
