"""
Job Processors
==============
One async function per job type. Each simulates real work with a
short sleep and returns a result string. Two payload fields let you
exercise the retry mechanism during testing/demo:

  "duration": <seconds>       -> how long the simulated work takes
  "simulate_failure": true    -> forces an exception on the first
                                  N attempts (N = "fail_times", default 1)
"""

import asyncio
import random


async def _maybe_fail(payload: dict, attempt_number: int):
    if payload.get("simulate_failure"):
        fail_times = payload.get("fail_times", 1)
        if attempt_number <= fail_times:
            raise RuntimeError(
                f"Simulated failure on attempt {attempt_number}/{fail_times}"
            )


async def process_file_processing(payload: dict, attempt_number: int) -> str:
    duration = payload.get("duration", random.uniform(1, 3))
    await asyncio.sleep(duration)
    await _maybe_fail(payload, attempt_number)
    filename = payload.get("filename", "unknown_file")
    return f"Processed file '{filename}' successfully in {duration:.2f}s"


async def process_data_transformation(payload: dict, attempt_number: int) -> str:
    duration = payload.get("duration", random.uniform(1, 2))
    await asyncio.sleep(duration)
    await _maybe_fail(payload, attempt_number)
    records = payload.get("record_count", 0)
    return f"Transformed {records} records successfully"


async def process_email_sending(payload: dict, attempt_number: int) -> str:
    duration = payload.get("duration", random.uniform(0.5, 1.5))
    await asyncio.sleep(duration)
    await _maybe_fail(payload, attempt_number)
    recipient = payload.get("to", "unknown@example.com")
    return f"Email sent to {recipient}"


async def process_report_generation(payload: dict, attempt_number: int) -> str:
    duration = payload.get("duration", random.uniform(2, 4))
    await asyncio.sleep(duration)
    await _maybe_fail(payload, attempt_number)
    report_name = payload.get("report_name", "report")
    return f"Report '{report_name}' generated successfully"


PROCESSORS = {
    "file_processing": process_file_processing,
    "data_transformation": process_data_transformation,
    "email_sending": process_email_sending,
    "report_generation": process_report_generation,
}
