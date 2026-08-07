# Async Job Processing System

A backend system for submitting long-running jobs and processing them
asynchronously with concurrent background workers. Built with FastAPI,
SQLAlchemy, SQLite and Python's `asyncio`.

## Architecture Overview

```
app/
├── main.py                # FastAPI app + startup/shutdown (starts/stops workers)
├── core/
│   ├── config.py           # All settings (worker count, retry limits, rate limits, etc.)
│   ├── database.py         # SQLAlchemy engine/session
│   ├── logger.py           # Structured JSON logging
│   └── rate_limiter.py     # Sliding-window rate limiter for job submission
├── models/
│   └── job.py               # Job table + Status/Priority/Type enums, dead-letter flag
├── schemas/
│   └── job.py                # Pydantic request/response models
├── routes/
│   ├── jobs.py                # POST/GET/DELETE /api/jobs — submit, list, get, cancel
│   └── dashboard.py           # GET /api/dashboard/stats, /queue, /dead-letter
├── services/
│   └── job_service.py         # DB read/write logic used by routes + workers
├── queue/
│   └── queue_manager.py       # Priority + FIFO in-memory queue
└── workers/
    ├── worker.py               # Worker pool: dequeue -> process -> retry/complete
    └── job_processors.py       # One async function per job type (simulated work)

static/
└── index.html              # Simple dashboard UI (served at /dashboard-ui/)
```

This follows a clean, layered design: **routes** only handle HTTP concerns,
**services** hold DB logic, the **queue** layer is purely about ordering jobs,
and the **worker** layer is purely about executing them. Nothing but
`worker.py` talks to both the queue and the database directly, which keeps
the retry/failure logic in one place.

## Queue Processing Flow

1. `POST /api/jobs` validates the request, writes a `Job` row to the
   database with status `PENDING`, and pushes the job id onto the
   `QueueManager`.
2. The queue is an `asyncio.PriorityQueue` where each entry is
   `(priority_rank, sequence_number, job_id)`. `priority_rank` makes
   `high` jobs pop before `medium`/`low`; `sequence_number` is a
   monotonically increasing counter so jobs of the **same** priority
   are still processed in **FIFO** order.
3. A free worker calls `dequeue()`, which blocks until a job id is
   available, then loads the full job row from the database.
4. The job status is set to `RUNNING` and the matching processor
   function (by `job_type`) is executed.
5. **On success:** status → `COMPLETED`, result and processing time saved.
6. **On failure:** `retries` is incremented.
   - If `retries < max_retries`: status goes back to `PENDING`, the job
     is logged as a retry, and it is re-enqueued after a short backoff.
   - If retries are exhausted: status → `FAILED` with the error message
     recorded.
7. On process restart, any job still `PENDING` from a previous run is
   reloaded into the queue on startup, so jobs are never silently lost.

## Worker Design

- Workers are `asyncio` tasks (not OS processes/threads) launched from
  the FastAPI `lifespan` handler, so they start automatically with the
  API and run independently of any single request.
- `WORKER_COUNT` (default 3, in `app/core/config.py`) controls how many
  jobs are processed **concurrently**.
- Each job is processed inside its own `try/except`, so one failing job
  never affects other jobs or crashes the worker.
- Each worker's outer loop is also wrapped in `try/except` — if
  something unexpected goes wrong, it's logged and the worker keeps
  running instead of dying silently (graceful crash handling).
- Retry limit and retry backoff are configurable via environment
  variables (`DEFAULT_MAX_RETRIES`, `RETRY_BACKOFF_SECONDS`) or per-job
  via the `max_retries` field in the submission payload.

## Job Types

| job_type              | Simulates                          |
|------------------------|-------------------------------------|
| `file_processing`      | Reading/processing a file           |
| `data_transformation`  | Transforming a batch of records     |
| `email_sending`        | Sending an email                    |
| `report_generation`    | Generating a report                 |

Each processor sleeps for a short, configurable duration to simulate
real work. Two optional payload fields are useful for demoing/testing
the retry mechanism:
- `"simulate_failure": true` — forces the job to fail
- `"fail_times": 2` — number of attempts that fail before it succeeds

## API Endpoints

| Method | Endpoint                    | Description                              |
|--------|------------------------------|--------------------------------------------|
| POST   | `/api/jobs`                  | Submit a new job (rate limited, see below) |
| GET    | `/api/jobs`                  | List jobs (filter by status/type/priority) |
| GET    | `/api/jobs/{job_id}`         | Get a single job's status/result           |
| DELETE | `/api/jobs/{job_id}`         | Cancel a job — only while still `pending`  |
| GET    | `/api/dashboard/stats`       | Total/pending/running/completed/failed/cancelled/dead_letter, avg time, success rate |
| GET    | `/api/dashboard/queue`       | Live queue size by priority                |
| GET    | `/api/dashboard/dead-letter` | Jobs that permanently failed (exhausted retries) |
| GET    | `/docs`                      | Interactive Swagger UI                     |
| GET    | `/dashboard-ui/`             | Simple visual dashboard (submit jobs, live stats, recent jobs table) |

### Bonus features included

Beyond the 6 core features, three bonus items from the brief are implemented:

- **Job cancellation** — `DELETE /api/jobs/{job_id}` sets status to `cancelled`, but only while the job is still `pending`. A job that's already `running` can't be safely stopped mid-execution, so cancelling it returns `409 Conflict`. Workers also check for cancellation right before starting, in case a job was cancelled the instant before a worker picked it up.
- **Dead-letter queue** — every job that permanently fails (exhausts `max_retries`) is flagged `is_dead_letter` and viewable via `GET /api/dashboard/dead-letter`, separately from jobs that are simply still retrying.
- **Rate limiting** — `POST /api/jobs` is protected by a sliding-window limiter (default: 20 submissions per 60 seconds per client IP). Exceeding it returns `429` with a message telling you how long to wait. Configurable via `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`.
- **Dashboard UI** — a small static HTML/JS page (`static/index.html`, no build step, no framework) served at `/dashboard-ui/`. It polls the existing API endpoints every 2 seconds — live stat cards, a job submission form, and a recent-jobs table with cancel buttons for pending jobs.

### Example: submit a job

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
        "job_type": "report_generation",
        "priority": "high",
        "payload": {"report_name": "Q1 Sales", "duration": 2}
      }'
```

### Example: submit a job that fails twice, then succeeds (to demo retries)

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
        "job_type": "data_transformation",
        "priority": "medium",
        "payload": {"record_count": 500, "simulate_failure": true, "fail_times": 2},
        "max_retries": 5
      }'
```

## Setup Instructions (VS Code)

1. Open the `job_queue_system` folder in VS Code.
2. Open a terminal in VS Code (`` Ctrl+` ``) and create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # macOS/Linux
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the server (this also starts the worker pool automatically):
   ```bash
   uvicorn app.main:app --reload
   ```
5. Open Swagger UI at **http://127.0.0.1:8000/docs** to submit and inspect
   jobs interactively, or use `curl`/Postman against the endpoints above.
6. Job data persists in `jobs.db` (SQLite, auto-created). Logs are written
   to `logs/app.log` as structured JSON, alongside console output.

No Redis, Celery, or Docker installation is required — the queue and
worker pool are implemented in-process with `asyncio`, and the database
is a local SQLite file, per the assignment's "custom implementation /
SQLite" option.

## Configuration

All tunables live in `app/core/config.py` and can be overridden with
environment variables:

| Variable                | Default         | Meaning                          |
|--------------------------|------------------|------------------------------------|
| `WORKER_COUNT`            | `3`              | Concurrent workers                |
| `DEFAULT_MAX_RETRIES`     | `3`              | Retry attempts per job (if not set on the job itself) |
| `RETRY_BACKOFF_SECONDS`   | `2`              | Delay before a failed job is retried |
| `DATABASE_URL`            | `sqlite:///./jobs.db` | DB connection string        |
| `RATE_LIMIT_MAX_REQUESTS` | `20`             | Max job submissions per window     |
| `RATE_LIMIT_WINDOW_SECONDS` | `60`           | Rate limit window length (seconds) |

## Notes on Requirements Coverage

**Core features**
- **Job Submission API** — `POST /api/jobs` (type, payload, priority) 
- **Async Processing** — `asyncio` workers, status transitions Pending → Running → Completed/Failed 
- **Queue Management** — FIFO + priority queue, configurable retry limits 
- **Worker System** — independent of API request cycle, concurrent, crash-safe 
- **Monitoring** — `/api/dashboard/stats`, `/api/dashboard/queue`, `/dashboard-ui/` 
- **Logging & Error Handling** — structured JSON logs for submission, start, completion, retries, and permanent failures, in `logs/app.log` 

**Bonus features implemented**
- Job cancellation 
- Dead-letter queue 
- Rate limiting 
- Simple dashboard UI 

**Bonus features not implemented** (all optional per the brief): scheduled/cron jobs, WebSocket live updates, Dockerized deployment.

## Scalability Considerations

This implementation is single-process by design (in-memory queue + SQLite),
which is appropriate for the scope of this assignment but has natural
limits. If this needed to scale further:

- **Queue**: swap the in-memory `asyncio.PriorityQueue` for Redis (via
  Redis Queue or Celery) so multiple separate worker *processes* — even
  on different machines — can pull from the same queue, instead of being
  limited to `asyncio` tasks inside one process.
- **Database**: move from SQLite to PostgreSQL, which handles concurrent
  writes from multiple worker processes far better than SQLite's
  single-writer model.
- **Workers**: run several worker containers/processes (horizontal
  scaling) instead of just increasing `WORKER_COUNT` within one process,
  so throughput isn't capped by a single machine's CPU.
- **Rate limiting**: the current limiter is in-memory and per-process;
  a multi-instance deployment would need a shared store (e.g. Redis) so
  limits are enforced across all instances, not per-instance.
- **Dashboard**: for very high job volumes, the dashboard stats queries
  (simple `COUNT`/`AVG` aggregates today) would benefit from caching or
  a read replica rather than querying the primary DB on every poll.
