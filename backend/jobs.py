"""Tiny in-memory job store so long Claid calls don't sit inside one HTTP request.

The browser starts a job, gets an id back straight away, then polls until it is done.
Jobs live in memory only, so a server restart forgets them.
"""
import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable

TTL = 3600  # forget finished jobs after an hour

_jobs: dict[str, dict[str, Any]] = {}


def _sweep() -> None:
    cutoff = time.time() - TTL
    for job_id in [k for k, v in _jobs.items() if v["done_at"] and v["done_at"] < cutoff]:
        _jobs.pop(job_id, None)


def start(factory: Callable[[], Awaitable[Any]]) -> str:
    """Run factory() in the background and return the job id."""
    _sweep()
    job_id = uuid.uuid4().hex
    _jobs[job_id] = {"status": "running", "result": None, "error": None, "done_at": None}

    async def runner() -> None:
        job = _jobs[job_id]
        try:
            job["result"] = await factory()
            job["status"] = "done"
        except Exception as e:  # reported to the browser as-is
            job["error"] = str(e)
            job["status"] = "error"
        finally:
            job["done_at"] = time.time()

    asyncio.create_task(runner())
    return job_id


def get(job_id: str) -> dict[str, Any] | None:
    job = _jobs.get(job_id)
    if not job:
        return None
    return {"status": job["status"], "result": job["result"], "error": job["error"]}
