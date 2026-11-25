"""
Production AI Agent — Part 6 Final Project.
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r as redis_conn
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    """Định dạng mọi dòng log của app thành 1 JSON object hợp lệ."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("production_agent")
logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
logger.handlers = [handler]
logger.propagate = False


def log_json(level: int, event: str, **fields) -> None:
    logger.log(level, event, extra={"extra_fields": {"event": event, **fields}})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management: startup & graceful shutdown (SIGTERM)."""
    log_json(
        logging.INFO,
        "startup",
        environment=settings.environment,
        port=settings.port,
    )
    yield
    log_json(logging.INFO, "shutdown_start", environment=settings.environment)
    try:
        redis_conn.close()
    except Exception:
        pass
    log_json(logging.INFO, "shutdown_complete")


app = FastAPI(title="Production AI Agent", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Không để lộ stack trace ra client khi có lỗi không mong muốn."""
    log_json(logging.ERROR, "unhandled_error", path=request.url.path, error=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = Field(default=None, max_length=128)


@app.get("/health")
def health():
    """Liveness probe: luôn trả 200 khi process còn chạy (không phụ thuộc Redis)."""
    return {
        "status": "ok",
        "environment": settings.environment,
    }


@app.get("/ready")
def ready():
    """Readiness probe: 200 khi Redis sẵn sàng, 503 khi mất kết nối Redis."""
    if not redis_healthy():
        log_json(logging.WARNING, "readiness_failed", reason="redis_unavailable")
        raise HTTPException(status_code=503, detail="Redis is not ready")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    """Endpoint chính: Auth → Rate Limit → Cost Guard → LLM → Record Cost."""
    start = time.perf_counter()
    check_rate_limit(api_key)
    check_budget()

    answer = llm_ask(body.question)
    input_tokens = max(1, len(body.question) // 4)
    output_tokens = max(1, len(answer) // 4)
    cost_usd = record_cost(input_tokens, output_tokens)

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    log_json(
        logging.INFO,
        "ask_completed",
        path="/ask",
        status=200,
        ms=elapsed_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost_usd, 6),
    )
    return {
        "question": body.question,
        "answer": answer,
        "cost_usd": round(cost_usd, 6),
    }
