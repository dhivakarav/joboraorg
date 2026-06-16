"""Structured JSON logging.

Emits one JSON line per log record so logs are queryable in production
aggregators (CloudWatch, Loki, Datadog). A request-logging middleware records
method, path, status, duration, and a per-request ID for tracing.
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        # Merge any structured extras attached via logger.info(..., extra={...}).
        for key, val in getattr(record, "extra_fields", {}).items():
            payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Quiet noisy access logs; our middleware emits structured request logs.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False


_logger = logging.getLogger("jobara.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request_id_ctx.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = (time.perf_counter() - start) * 1000
            _logger.exception(
                "request failed",
                extra={"extra_fields": {
                    "method": request.method, "path": request.url.path,
                    "duration_ms": round(duration, 1),
                }},
            )
            raise
        duration = (time.perf_counter() - start) * 1000
        # Skip health/readiness chatter.
        if request.url.path not in ("/api/health", "/api/ready"):
            _logger.info(
                "request",
                extra={"extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration, 1),
                }},
            )
        response.headers["x-request-id"] = rid
        return response
