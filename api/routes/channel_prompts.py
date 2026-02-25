from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from api.auth import decode_token
import db

router = APIRouter()
security = HTTPBearer()


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


class ChannelPromptCreate(BaseModel):
    channel_id: str
    guild_id: str
    system_prompt: str


@router.get("")
async def list_channel_prompts(guild_id: str = "", _=Depends(require_auth)):
    try:
        if guild_id:
            return await db.list_channel_prompts(guild_id)
        database = await db.get_db()
        cursor = await database.execute("SELECT * FROM channel_prompts")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def set_channel_prompt(item: ChannelPromptCreate, _=Depends(require_auth)):
    try:
        await db.set_channel_prompt(item.channel_id, item.guild_id, item.system_prompt)
        return item.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{channel_id}")
async def delete_channel_prompt(channel_id: str, _=Depends(require_auth)):
    try:
        await db.delete_channel_prompt(channel_id)
        return {"deleted": True, "channel_id": channel_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))