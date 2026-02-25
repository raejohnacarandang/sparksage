from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

import importlib.util
import os

# Load bot/services/ai.py directly to avoid import shadowing by top-level bot.py
ai_path = os.path.join(os.path.dirname(__file__), "..", "..", "bot", "services", "ai.py")
ai_path = os.path.abspath(ai_path)
spec = importlib.util.spec_from_file_location("bot_services_ai", ai_path)
ai_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_module)  # type: ignore
ai_client = getattr(ai_module, "ai_client")

router = APIRouter()


class ReviewRequest(BaseModel):
    content: str


@router.post("")
async def review(body: ReviewRequest):
    if not body.content:
        return {"error": "Content required"}

    try:
        result = await ai_client.review(body.content)
        return result
    except Exception as e:
        return {"error": str(e)}
