"""健康数据趋势接口（M9 扩展）：体重/血压记录（需登录）

说明：数值型指标记录，前端以折线图展示趋势；数据仅服务展示与自我管理，
不构成医学判断。
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.config import settings
from app.dao import health_dao

router = APIRouter(prefix="/api/health", tags=["健康数据"])


class HealthRecordCreate(BaseModel):
    record_type: str = Field(..., description="记录类型：weight/systolic/diastolic")
    value: float = Field(..., description="数值（体重 kg / 血压 mmHg）")
    note: str = Field(default="", max_length=200)
    record_date: str | None = Field(default=None, description="记录日期 YYYY-MM-DD，缺省为今天")


def _require_db() -> None:
    if not settings.DB_ENABLED:
        raise HTTPException(status_code=503, detail="健康记录功能未启用：请启动 MySQL 并设置 MYSQL_ENABLED=1 后重启服务")


@router.post("/records")
def add_record(req: HealthRecordCreate, username: str = Depends(get_current_user)):
    """写入一条健康记录（同日期同类型覆盖旧值）"""
    _require_db()
    if req.record_type not in health_dao.RECORD_TYPES:
        raise HTTPException(status_code=400, detail="record_type 仅支持 weight/systolic/diastolic")
    if req.record_type == "weight" and not 1 <= req.value <= 500:
        raise HTTPException(status_code=400, detail="体重数值不合理（1-500kg）")
    if req.record_type in ("systolic", "diastolic") and not 20 <= req.value <= 300:
        raise HTTPException(status_code=400, detail="血压数值不合理（20-300mmHg）")
    if req.record_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", req.record_date):
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
    health_dao.add_record(username, req.record_type, req.value, req.note, req.record_date)
    return {"message": "记录成功", "latest": health_dao.latest_values(username)}


@router.get("/records")
def list_records(
    record_type: str = Query(..., description="记录类型：weight/systolic/diastolic"),
    days: int = Query(default=30, ge=1, le=365, description="查询最近 N 天"),
    username: str = Depends(get_current_user),
):
    """查询某类指标最近 N 天记录（按日期升序，供折线图）"""
    _require_db()
    if record_type not in health_dao.RECORD_TYPES:
        raise HTTPException(status_code=400, detail="record_type 仅支持 weight/systolic/diastolic")
    return {
        "record_type": record_type,
        "unit": health_dao.RECORD_TYPES[record_type],
        "records": health_dao.list_records(username, record_type, days),
    }


@router.delete("/records/{record_id}")
def delete_record(record_id: int, username: str = Depends(get_current_user)):
    """删除一条记录"""
    _require_db()
    if not health_dao.delete_record(username, record_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"message": "已删除"}


@router.get("/summary")
def health_summary(username: str = Depends(get_current_user)):
    """各类指标最新值（首页健康卡片）"""
    _require_db()
    return {"latest": health_dao.latest_values(username)}
