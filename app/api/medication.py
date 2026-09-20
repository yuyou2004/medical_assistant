"""用药提醒接口（M9 扩展）：用药计划 CRUD + 今日清单 + 服药打卡（需登录）

说明：提醒弹窗由前端实现（页面打开时按计划时间点用浏览器 Notification 通知，
本机演示方案；生产环境应换 Redis 定时任务 + 推送渠道）。后端负责计划、
打卡记录与今日清单。
"""
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.config import settings
from app.dao import medication_dao

router = APIRouter(prefix="/api/medications", tags=["用药提醒"])

_TIME_POINT_RE = r"^(?:[01]\d|2[0-3]):[0-5]\d$"


class MedicationCreate(BaseModel):
    medicine_name: str = Field(..., min_length=1, max_length=60, description="药名")
    times_per_day: int = Field(..., ge=1, le=6, description="每日服药次数")
    time_points: list[str] = Field(..., description="服药时间点 HH:MM，数量应与次数一致")
    note: str = Field(default="", max_length=200, description="备注（饭前/饭后等）")


class MedicationUpdate(BaseModel):
    medicine_name: str | None = Field(default=None, min_length=1, max_length=60)
    times_per_day: int | None = Field(default=None, ge=1, le=6)
    time_points: list[str] | None = None
    note: str | None = Field(default=None, max_length=200)
    active: bool | None = None


class TakeLogRequest(BaseModel):
    medication_id: int = Field(..., description="用药计划 id")
    time_point: str = Field(..., description="打卡时段 HH:MM")
    log_date: str | None = Field(default=None, description="补卡日期 YYYY-MM-DD，缺省为今天")


def _require_db() -> None:
    if not settings.DB_ENABLED:
        raise HTTPException(status_code=503, detail="用药提醒功能未启用：请启动 MySQL 并设置 MYSQL_ENABLED=1 后重启服务")


def _validate_time_points(req: MedicationCreate) -> None:
    if len(req.time_points) != req.times_per_day:
        raise HTTPException(status_code=400, detail="时间点数量应与每日服药次数一致")
    if len(set(req.time_points)) != len(req.time_points):
        raise HTTPException(status_code=400, detail="时间点不能重复")
    if not all(re.fullmatch(_TIME_POINT_RE, tp) for tp in req.time_points):
        raise HTTPException(status_code=400, detail="时间点格式应为 HH:MM")


@router.get("")
def my_medications(username: str = Depends(get_current_user)):
    """我的用药计划"""
    _require_db()
    return {"medications": medication_dao.list_medications(username)}


@router.post("")
def create_medication(req: MedicationCreate, username: str = Depends(get_current_user)):
    """新增用药计划"""
    _require_db()
    _validate_time_points(req)
    med_id = medication_dao.create_medication(
        username, req.medicine_name, req.times_per_day, req.time_points, req.note
    )
    return {"medication_id": med_id, "message": "用药计划已创建"}


@router.put("/{med_id}")
def update_medication(med_id: int, req: MedicationUpdate, username: str = Depends(get_current_user)):
    """修改用药计划（含启用/停用）"""
    _require_db()
    if medication_dao.get_medication(username, med_id) is None:
        raise HTTPException(status_code=404, detail="用药计划不存在")
    fields = req.model_dump(exclude_none=True)
    if "time_points" in fields:
        times = fields["times_per_day"] or len(fields["time_points"])
        if len(fields["time_points"]) != times:
            raise HTTPException(status_code=400, detail="时间点数量应与每日服药次数一致")
        if not all(re.fullmatch(_TIME_POINT_RE, tp) for tp in fields["time_points"]):
            raise HTTPException(status_code=400, detail="时间点格式应为 HH:MM")
    if not fields or not medication_dao.update_medication(username, med_id, **fields):
        raise HTTPException(status_code=400, detail="没有可更新的字段")
    return {"message": "已更新"}


@router.delete("/{med_id}")
def delete_medication(med_id: int, username: str = Depends(get_current_user)):
    """删除用药计划"""
    _require_db()
    if not medication_dao.delete_medication(username, med_id):
        raise HTTPException(status_code=404, detail="用药计划不存在")
    return {"message": "已删除"}


@router.get("/checklist/today")
def today_checklist(username: str = Depends(get_current_user)):
    """今日服药清单（计划 × 时段 → 是否已打卡）"""
    _require_db()
    return medication_dao.today_checklist(username)


@router.post("/logs")
def take_log(req: TakeLogRequest, username: str = Depends(get_current_user)):
    """服药打卡（同一计划同日同时段只记一次）"""
    _require_db()
    if not medication_dao.take_log(username, req.medication_id, req.time_point, req.log_date):
        raise HTTPException(status_code=400, detail="打卡失败：计划不存在或时段不在计划内")
    return {"message": "打卡成功", **medication_dao.today_checklist(username)}
