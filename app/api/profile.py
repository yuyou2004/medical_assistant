"""健康档案接口（M8 扩展）：GET/PUT /api/profile（需登录）

档案会在多智能体会诊时作为上下文携带（/api/agent/chat 传 include_profile=true），
让问诊与回答能参考用户的病史、过敏史等。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.config import settings
from app.dao import db, profile_dao

router = APIRouter(prefix="/api/profile", tags=["健康档案"])


class ProfileIn(BaseModel):
    real_name: str = Field(default="", max_length=30)
    gender: str = Field(default="", max_length=10)
    age: int = Field(default=0, ge=0, le=150)
    height: str = Field(default="", max_length=10)
    weight: str = Field(default="", max_length=10)
    medical_history: list[str] = Field(default_factory=list, max_length=20)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    medications: list[str] = Field(default_factory=list, max_length=20)


def _require_db() -> None:
    if not settings.DB_ENABLED:
        raise HTTPException(status_code=503, detail="健康档案未启用：请启动 MySQL 并设置 MYSQL_ENABLED=1 后重启服务")


@router.get("")
def get_profile(username: str = Depends(get_current_user)):
    """读取当前用户健康档案"""
    _require_db()
    return profile_dao.get_profile(username)


@router.put("")
def save_profile(req: ProfileIn, username: str = Depends(get_current_user)):
    """保存（创建或更新）健康档案"""
    _require_db()
    profile_dao.upsert_profile(username, req.model_dump())
    return {"message": "健康档案已保存，多智能体会诊时将自动携带"}


@router.get("/summary")
def profile_summary(username: str = Depends(get_current_user)):
    """档案是否已填写 + 摘要（前端会诊开关用）"""
    _require_db()
    p = profile_dao.get_profile(username)
    filled = bool(p["real_name"] or p["medical_history"] or p["allergies"] or p["medications"] or p["age"])
    return {"filled": filled, "summary": profile_dao.format_profile(p)}
