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


class PermissionCreate(BaseModel):
    command_name: str
    guild_id: str
    role_id: str


@router.get("")
async def list_permissions(guild_id: str = "", _=Depends(require_auth)):
    """List all command permissions for a guild."""
    try:
        perms = await db.get_command_permissions(guild_id)
        return perms
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def add_permission(item: PermissionCreate, _=Depends(require_auth)):
    """Add a role restriction to a command."""
    try:
        await db.add_command_permission(item.command_name, item.guild_id, item.role_id)
        return {"success": True, **item.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def remove_permission(item: PermissionCreate, _=Depends(require_auth)):
    """Remove a role restriction from a command."""
    try:
        removed = await db.remove_command_permission(item.command_name, item.guild_id, item.role_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Permission not found")
        return {"deleted": True, **item.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))