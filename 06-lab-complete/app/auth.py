"""
API Key authentication (tiêu chí 6).
"""
import hmac
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Xác thực header X-API-Key. Thiếu hoặc sai key trả HTTP 401."""
    expected = settings.agent_api_key
    if not expected or not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )
    return api_key
