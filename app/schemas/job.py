"""
Pydantic schemas used by the API layer for request validation
and response serialization.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.models.job import JobStatus, JobPriority, JobType


class JobCreate(BaseModel):
    job_type: JobType
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: JobPriority = JobPriority.MEDIUM
    max_retries: Optional[int] = None


class JobResponse(BaseModel):
    id: str
    job_type: JobType
    payload: Dict[str, Any]
    priority: JobPriority
    status: JobStatus
    retries: int
    max_retries: int
    result: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class QueueStats(BaseModel):
    queue_size: int
    high_priority_pending: int
    medium_priority_pending: int
    low_priority_pending: int


class DashboardStats(BaseModel):
    total_jobs: int
    pending: int
    running: int
    completed: int
    failed: int
    cancelled: int
    dead_letter: int
    average_processing_time_seconds: Optional[float]
    success_rate_percent: Optional[float]
    queue: QueueStats
