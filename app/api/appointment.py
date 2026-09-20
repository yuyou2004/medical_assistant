"""预约挂号接口（M8 扩展）：创建 / 查询 / 取消（需登录）"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.config import settings
from app.dao import appointment_dao, db, hospital_dao

router = APIRouter(prefix="/api/appointments", tags=["预约挂号"])


class AppointmentCreate(BaseModel):
    hospital_id: int = Field(..., description="医院 id")
    department: str = Field(..., min_length=2, max_length=20)
    doctor: str = Field(..., min_length=2, max_length=20)
    visit_date: str = Field(..., description="就诊日期 YYYY-MM-DD")
    time_slot: str = Field(..., description="时段，如 08:00-10:00")
    patient_name: str = Field(..., min_length=2, max_length=30)
    patient_phone: str = Field(..., min_length=7, max_length=20)
    symptom: str = Field(default="", max_length=500)


def _require_db() -> None:
    if not settings.DB_ENABLED:
        raise HTTPException(status_code=503, detail="预约挂号功能未启用：请启动 MySQL 并设置 MYSQL_ENABLED=1 后重启服务")


@router.post("")
def create_appointment(req: AppointmentCreate, username: str = Depends(get_current_user)):
    """创建预约：校验医院/科室/排班/余号，成功返回挂号单"""
    _require_db()
    hospital = hospital_dao.get_hospital(req.hospital_id)
    if hospital is None:
        raise HTTPException(status_code=404, detail="医院不存在")
    if req.department not in hospital["departments"]:
        raise HTTPException(status_code=400, detail=f"该医院未开设「{req.department}」")
    if req.time_slot not in hospital_dao.TIME_SLOTS:
        raise HTTPException(status_code=400, detail="时段无效")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", req.visit_date):
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
    doctors = [d[0] for d in hospital_dao.DOCTORS.get(req.department, hospital_dao.DOCTORS["内科"])]
    if req.doctor not in doctors:
        raise HTTPException(status_code=400, detail="医生不存在于该科室排班")
    ok, result = appointment_dao.create(
        username, hospital["name"], req.department, req.doctor,
        req.visit_date, req.time_slot, req.patient_name, req.patient_phone, req.symptom,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=str(result))
    return {
        "appointment_id": result,
        "message": "预约成功，请按时携带身份证就诊（演示系统，无真实号源）",
        "ticket": {
            "hospital_name": hospital["name"],
            "hospital_address": hospital["address"],
            "department": req.department,
            "doctor": req.doctor,
            "visit_date": req.visit_date,
            "time_slot": req.time_slot,
            "patient_name": req.patient_name,
        },
    }


@router.get("")
def my_appointments(username: str = Depends(get_current_user)):
    """我的预约列表"""
    _require_db()
    return {"appointments": appointment_dao.list_by_user(username)}


@router.delete("/{appointment_id}")
def cancel_appointment(appointment_id: int, username: str = Depends(get_current_user)):
    """取消预约"""
    _require_db()
    if not appointment_dao.cancel(appointment_id, username):
        raise HTTPException(status_code=404, detail="预约不存在或已取消")
    return {"message": "已取消预约"}
