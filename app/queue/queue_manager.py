"""
Queue Manager
=============
Wraps asyncio.PriorityQueue to give:
  - Priority-based execution (high before medium before low)
  - FIFO ordering *within* the same priority level
  - Visibility into current queue composition for the dashboard

Ordering trick: each entry is (priority_rank, sequence_number, job_id).
priority_rank makes high-priority jobs sort first. sequence_number is a
monotonically increasing counter, so two jobs with the same priority
are still popped in the order they were enqueued (FIFO tie-break).
"""

import asyncio
import itertools
from app.models.job import JobPriority

PRIORITY_RANK = {
    JobPriority.HIGH: 0,
    JobPriority.MEDIUM: 1,
    JobPriority.LOW: 2,
}


class QueueManager:
    def __init__(self):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._counter = itertools.count()
        # Track pending counts per priority for dashboard stats without
        # having to drain the queue.
        self._pending_counts = {
            JobPriority.HIGH: 0,
            JobPriority.MEDIUM: 0,
            JobPriority.LOW: 0,
        }

    async def enqueue(self, job_id: str, priority: JobPriority):
        rank = PRIORITY_RANK[priority]
        seq = next(self._counter)
        await self._queue.put((rank, seq, job_id, priority))
        self._pending_counts[priority] += 1

    async def dequeue(self) -> str:
        rank, seq, job_id, priority = await self._queue.get()
        self._pending_counts[priority] -= 1
        return job_id

    def task_done(self):
        self._queue.task_done()

    def size(self) -> int:
        return self._queue.qsize()

    def stats(self) -> dict:
        return {
            "queue_size": self.size(),
            "high_priority_pending": self._pending_counts[JobPriority.HIGH],
            "medium_priority_pending": self._pending_counts[JobPriority.MEDIUM],
            "low_priority_pending": self._pending_counts[JobPriority.LOW],
        }


# Single shared instance used by both the API routes and the workers.
queue_manager = QueueManager()
