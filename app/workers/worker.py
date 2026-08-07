"""
Worker Pool
===========
Runs independently of the request/response cycle of the API. On
startup, N asyncio worker tasks are launched; each one continuously
pulls a job id from the shared QueueManager and processes it.

Reliability behaviour:
  - Each job is processed inside its own try/except so one bad job
    never kills a worker.
  - The worker's outer loop is also wrapped in try/except so an
    unexpected crash is logged and the worker keeps running instead
    of silently dying (graceful crash handling).
  - Failed jobs are retried up to `max_retries` times (with a short
    backoff) before being marked FAILED for good.
  - On startup, any job left PENDING from a previous run (e.g. the
    process was killed mid-queue) is reloaded into the queue so no
    job is lost.
"""

import asyncio
import json
import time
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.logger import get_logger, log_event
from app.models.job import Job, JobStatus
from app.queue.queue_manager import queue_manager
from app.services.job_service import get_pending_jobs_ordered
from app.workers.job_processors import PROCESSORS

logger = get_logger("worker")

_worker_tasks: list[asyncio.Task] = []


async def _process_job(job_id: str, worker_name: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            log_event(logger, "Job not found, skipping", level="warning", job_id=job_id)
            return
        if job.status == JobStatus.FAILED and job.retries >= job.max_retries:
            # Defensive guard: never re-run a job that already exhausted retries.
            return
        if job.status == JobStatus.CANCELLED:
            # Job was cancelled by the user while it was still sitting in
            # the queue — skip it instead of processing.
            log_event(logger, "Skipping cancelled job", job_id=job.id, worker=worker_name)
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        attempt_number = job.retries + 1
        log_event(
            logger,
            "Job started",
            job_id=job.id,
            job_type=job.job_type.value,
            worker=worker_name,
            attempt=attempt_number,
        )

        payload = json.loads(job.payload)
        processor = PROCESSORS[job.job_type.value]

        start = time.monotonic()
        try:
            result = await processor(payload, attempt_number)
            elapsed = time.monotonic() - start

            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.now(timezone.utc)
            job.processing_time_seconds = round(elapsed, 3)
            db.commit()

            log_event(
                logger,
                "Job completed",
                job_id=job.id,
                worker=worker_name,
                duration_seconds=job.processing_time_seconds,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            job.retries += 1

            if job.retries < job.max_retries:
                job.status = JobStatus.PENDING
                job.error_message = f"Attempt {attempt_number} failed: {exc}"
                db.commit()

                log_event(
                    logger,
                    "Job failed, scheduling retry",
                    level="warning",
                    job_id=job.id,
                    worker=worker_name,
                    attempt=attempt_number,
                    retries_left=job.max_retries - job.retries,
                    error=str(exc),
                )

                await asyncio.sleep(settings.RETRY_BACKOFF_SECONDS)
                await queue_manager.enqueue(job.id, job.priority)
            else:
                job.status = JobStatus.FAILED
                job.error_message = f"Attempt {attempt_number} failed: {exc}"
                job.completed_at = datetime.now(timezone.utc)
                job.processing_time_seconds = round(elapsed, 3)
                job.is_dead_letter = 1
                db.commit()

                log_event(
                    logger,
                    "Job permanently failed, moved to dead-letter",
                    level="error",
                    job_id=job.id,
                    worker=worker_name,
                    total_attempts=attempt_number,
                    error=str(exc),
                )
    finally:
        db.close()


async def _worker_loop(worker_name: str):
    log_event(logger, "Worker started", worker=worker_name)
    while True:
        try:
            job_id = await queue_manager.dequeue()
            try:
                await _process_job(job_id, worker_name)
            finally:
                queue_manager.task_done()
        except asyncio.CancelledError:
            log_event(logger, "Worker shutting down", worker=worker_name)
            raise
        except Exception as exc:
            # Graceful crash handling: log and keep the worker alive
            # instead of letting an unexpected error kill the loop.
            log_event(
                logger,
                "Worker encountered an unexpected error, continuing",
                level="error",
                worker=worker_name,
                error=str(exc),
            )


async def start_workers():
    """Reload any pending jobs from a previous run, then spin up the pool."""
    db = SessionLocal()
    try:
        pending_jobs = get_pending_jobs_ordered(db)
        for job in pending_jobs:
            await queue_manager.enqueue(job.id, job.priority)
        if pending_jobs:
            log_event(
                logger,
                "Reloaded pending jobs from previous run",
                count=len(pending_jobs),
            )
    finally:
        db.close()

    for i in range(settings.WORKER_COUNT):
        worker_name = f"worker-{i + 1}"
        task = asyncio.create_task(_worker_loop(worker_name))
        _worker_tasks.append(task)

    log_event(logger, "Worker pool started", worker_count=settings.WORKER_COUNT)


async def stop_workers():
    for task in _worker_tasks:
        task.cancel()
    await asyncio.gather(*_worker_tasks, return_exceptions=True)
    log_event(logger, "Worker pool stopped")
