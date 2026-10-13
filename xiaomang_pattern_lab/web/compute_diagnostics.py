"""Diagnostics around the existing slot; no scheduling, timeout or cancellation."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import os
import threading
from time import perf_counter
from uuid import uuid4

from .http_errors import WebError


class ComputeTask:
    def __init__(self, owner, endpoint, dto):
        self.owner = owner
        self.request_id = uuid4().hex
        self.task_id = uuid4().hex
        self.endpoint = endpoint
        self.document_ref = sha256(dto.document_id.encode()).hexdigest()[:16]
        self.revision = dto.document_revision
        self.element_count = len(dto.document.get("elements", []))
        self.instance_count = None  # Unknown until authoritative planning completes.
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.started = perf_counter()
        self.stage = "acquired"
        self.error_type = None

    def phase(self, stage, *, instance_count=None):
        with self.owner.guard:
            self.stage = stage
            if instance_count is not None:
                self.instance_count = instance_count
            self.owner.emit("stage", self)

    def failed(self, error):
        self.error_type = type(error).__name__  # Never log exception text/paths.

    def snapshot(self):
        return {"request_id": self.request_id, "task_id": self.task_id,
                "pid": os.getpid(), "endpoint": self.endpoint,
                "document_ref": self.document_ref, "revision": self.revision,
                "source_element_count": self.element_count,
                "instance_count": self.instance_count, "started_at": self.started_at,
                "stage": self.stage, "elapsed_ms": round((perf_counter() - self.started) * 1000, 2)}


class ComputeDiagnostics:
    def __init__(self, slot):
        self.slot = slot
        self.guard = threading.RLock()
        self.active = {}
        # Uvicorn configures this logger at INFO without changing root logging.
        self.logger = logging.getLogger("uvicorn.error")

    def emit(self, event, task, **fields):
        try:
            self.logger.info("compute_task %s", json.dumps(
                {"event": event, "recorded_at": datetime.now(timezone.utc).isoformat(),
                 **task.snapshot(), **fields}, separators=(",", ":")))
        except Exception:
            # A diagnostic handler failure must not strand or release CPU work.
            pass

    @contextmanager
    def task(self, endpoint, dto):
        with self.guard:
            task = ComputeTask(self, endpoint, dto)
            if self.slot is not None and not self.slot.acquire(blocking=False):
                occupied = next(iter(self.active.values()), None)
                task.stage = "rejected_busy"
                self.emit("busy", task, task_id=None, started_at=None, elapsed_ms=None,
                          occupied=occupied.snapshot() if occupied else None)
                raise WebError("staging_busy", "测试站正在处理另一项三维任务，请稍后重试。")
            self.active[task.task_id] = task
            self.emit("start", task)
        try:
            yield task
        except BaseException as error:
            task.failed(error)
            raise
        finally:
            with self.guard:
                self.emit("end", task, outcome="error" if task.error_type else "completed",
                          error_type=task.error_type)
                # Same synchronous work lifetime and finally as the original routes.
                if self.slot is not None:
                    self.slot.release()
                del self.active[task.task_id]
                self.emit("released", task, slot_enforced=self.slot is not None)
