"""
Job model + status/priority enums.
"""

import enum
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.core.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JobType(str, enum.Enum):
    FILE_PROCESSING = "file_processing"
    DATA_TRANSFORMATION = "data_transformation"
    EMAIL_SENDING = "email_sending"
    REPORT_GENERATION = "report_generation"


def generate_id() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=generate_id)
    job_type = Column(Enum(JobType), nullable=False)
    payload = Column(Text, nullable=False, default="{}")
    priority = Column(Enum(JobPriority), nullable=False, default=JobPriority.MEDIUM)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING)

    retries = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)

    result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # True once a job has exhausted all retries and permanently failed.
    # Kept as its own flag (rather than inferring from status) so the
    # dead-letter list stays queryable even if status logic changes later.
    is_dead_letter = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
