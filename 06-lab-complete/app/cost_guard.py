"""
Cost guard (tiêu chí 8) — Theo dõi chi phí LLM trong Redis và chặn 402 khi vượt ngân sách.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _budget_key() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"cost:daily:{today}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    try:
        current = float(r.get(_budget_key()) or 0.0)
    except RedisError:
        raise HTTPException(status_code=503, detail="Budget backend unavailable")

    if current >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail="Daily LLM budget exceeded",
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí vào Redis, trả về chi phí request."""
    cost = (
        (input_tokens / 1000.0) * PRICE_INPUT_PER_1K
        + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    )
    key = _budget_key()
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(key, cost)
        pipe.expire(key, 48 * 3600)
        pipe.execute()
    except RedisError:
        pass
    return cost
