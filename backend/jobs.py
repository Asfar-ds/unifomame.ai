"""Tiny in-memory job store so long Claid calls don't sit inside one HTTP request.

The browser starts a job, gets an id back straight away, then polls until it is done.
Jobs live in memory only, so a server restart forgets them.
"""
import asyncio
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from .claid import ClaidError

TTL = 3600  # forget finished jobs after an hour

log = logging.getLogger("uniforma")

GENERIC_ERROR = "Something went wrong on our side. Please try again."

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
        except Exception as e:
            # ClaidError messages are written for the person using the app; anything
            # else (network, bugs) stays in the log and shows a generic line instead.
            log.exception("job %s failed", job_id)
            job["error"] = str(e) if isinstance(e, ClaidError) else GENERIC_ERROR
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
