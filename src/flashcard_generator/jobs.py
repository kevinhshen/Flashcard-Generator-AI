"""Bounded, in-memory background generation; no notes written to disk."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event, Lock
from time import monotonic
from uuid import uuid4

from .ai import Cancelled, safe_ai_error


class JobStore:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="recall")
        self.lock = Lock()
        self.jobs = {}

    def _prune(self):
        now = monotonic()
        expired = [
            key
            for key, job in self.jobs.items()
            if job["status"] not in {"queued", "running"} and now - job["updated"] > 1800
        ]
        for key in expired:
            del self.jobs[key]
        completed = [key for key, job in self.jobs.items() if job["status"] not in {"queued", "running"}]
        for key in completed[:-10]:
            del self.jobs[key]

    def submit(self, work):
        with self.lock:
            self._prune()
            if any(job["status"] in {"queued", "running"} for job in self.jobs.values()):
                raise ValueError("Generation is already running. Wait or cancel it before starting another.")
            key = uuid4().hex
            self.jobs[key] = {
                "status": "queued",
                "progress": "Queued",
                "updated": monotonic(),
                "cancel": Event(),
            }
        self.executor.submit(self._run, key, work)
        return key

    def _run(self, key, work):
        with self.lock:
            job = self.jobs[key]
            job["status"] = "running"
            event = job["cancel"]

        def progress(message):
            with self.lock:
                self.jobs[key].update(progress=message, updated=monotonic())

        try:
            if event.is_set():
                raise Cancelled()
            result = work(progress, event.is_set)
            if event.is_set():
                raise Cancelled()
            final = {"status": "completed", "result": result, "progress": "Complete"}
        except Exception as exc:
            error = safe_ai_error(exc)
            final = {
                "status": "cancelled" if error.code == "cancelled" else "failed",
                "error": str(error),
                "error_code": error.code,
            }
        with self.lock:
            self.jobs[key].update(**final, updated=monotonic())

    def get(self, key):
        with self.lock:
            self._prune()
            job = self.jobs.get(key)
            return deepcopy({k: v for k, v in job.items() if k not in {"cancel", "updated"}}) if job else None

    def cancel(self, key):
        with self.lock:
            job = self.jobs.get(key)
            if job is None:
                return False
            job["cancel"].set()
            if job["status"] in {"queued", "running"}:
                job["progress"] = "Cancelling after the current provider request…"
            return True
