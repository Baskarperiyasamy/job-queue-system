# Sample Run Output (for reference)

This is real output captured from running this exact project, so you know
what to expect when you run it yourself. (A live browser screenshot of
Swagger UI isn't available in this environment — run `uvicorn app.main:app
--reload` and open `http://127.0.0.1:8000/docs` to see it yourself; it will
look like the standard FastAPI interactive docs page, listing the Jobs and
Dashboard endpoints grouped by tag.)

## 1. Health check

```
GET / 
{"status":"ok","service":"Async Job Processing System"}
```

## 2. Submitting a job

```
POST /api/jobs
{"job_type":"report_generation","priority":"high","payload":{"report_name":"Q1 Sales","duration":1}}

Response:
{
  "id": "5a421fe4-91ed-4f41-8e3a-23d55bc8919f",
  "job_type": "report_generation",
  "payload": {"report_name": "Q1 Sales", "duration": 1},
  "priority": "high",
  "status": "pending",
  "retries": 0,
  "max_retries": 3,
  "result": null,
  "error_message": null,
  "created_at": "2026-08-04T05:49:02",
  "started_at": null,
  "completed_at": null,
  "processing_time_seconds": null
}
```

## 3. Job completed a few seconds later (GET /api/jobs/{id})

```
{
  "id": "5a421fe4-91ed-4f41-8e3a-23d55bc8919f",
  "job_type": "report_generation",
  "status": "completed",
  "retries": 0,
  "result": "Report 'Q1 Sales' generated successfully",
  "started_at": "2026-08-04T05:49:02.326031",
  "completed_at": "2026-08-04T05:49:03.331405",
  "processing_time_seconds": 1.001
}
```

## 4. Retry mechanism in action

Submitted with `"simulate_failure": true, "fail_times": 2, "max_retries": 5`:

```
{
  "id": "18e7d4f6-1345-4f6a-94cb-3e74bb03d100",
  "job_type": "data_transformation",
  "status": "completed",
  "retries": 2,
  "result": "Transformed 500 records successfully",
  "error_message": "Attempt 2 failed: Simulated failure on attempt 2/2",
  "processing_time_seconds": 1.0
}
```

Corresponding structured log entries (`logs/app.log`):

```json
{"timestamp": "2026-08-04 05:49:03", "level": "WARNING", "logger": "worker", "message": "Job failed, scheduling retry", "job_id": "18e7d4f6-...", "worker": "worker-3", "attempt": 1, "retries_left": 4, "error": "Simulated failure on attempt 1/2"}
{"timestamp": "2026-08-04 05:49:06", "level": "WARNING", "logger": "worker", "message": "Job failed, scheduling retry", "job_id": "18e7d4f6-...", "worker": "worker-3", "attempt": 2, "retries_left": 3, "error": "Simulated failure on attempt 2/2"}
```

## 5. Permanent failure (retries exhausted)

Submitted with `"simulate_failure": true, "fail_times": 99, "max_retries": 2`:

```
GET /api/dashboard/stats
{
  "total_jobs": 4,
  "pending": 0,
  "running": 0,
  "completed": 3,
  "failed": 1,
  "average_processing_time_seconds": 1.0,
  "success_rate_percent": 75.0,
  "queue": {
    "queue_size": 0,
    "high_priority_pending": 0,
    "medium_priority_pending": 0,
    "low_priority_pending": 0
  }
}
```

## 6. Dashboard stats endpoint

```
GET /api/dashboard/stats
{
  "total_jobs": 3,
  "pending": 0,
  "running": 0,
  "completed": 3,
  "failed": 0,
  "average_processing_time_seconds": 1.0,
  "success_rate_percent": 100.0,
  "queue": {"queue_size": 0, "high_priority_pending": 0, "medium_priority_pending": 0, "low_priority_pending": 0}
}
```
