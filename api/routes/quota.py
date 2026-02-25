from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from api.auth import decode_token
from utils.rate_limiter import _user_windows, _guild_windows, RATE_LIMIT_USER, RATE_LIMIT_GUILD
import time

router = APIRouter()
security = HTTPBearer()


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


@router.get("/api/quota/stats")
async def get_quota_stats(_=Depends(require_auth)):
    """Get current rate limit usage for all active users and guilds."""
    now = time.time()
    stats = []

    for user_id, window in _user_windows.items():
        # Clean expired entries
        while window and now - window[0] > 60:
            window.popleft()
        if window:
            used = len(window)
            stats.append({
                "id": user_id,
                "type": "user",
                "requests_used": used,
                "limit": RATE_LIMIT_USER,
                "remaining": max(0, RATE_LIMIT_USER - used),
            })

    for guild_id, window in _guild_windows.items():
        while window and now - window[0] > 60:
            window.popleft()
        if window:
            used = len(window)
            stats.append({
                "id": guild_id,
                "type": "guild",
                "requests_used": used,
                "limit": RATE_LIMIT_GUILD,
                "remaining": max(0, RATE_LIMIT_GUILD - used),
            })

    return stats