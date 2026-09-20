"""医院接口（M8 扩展）：GET /api/hospitals 医院查询 + GET /api/hospitals/schedule 挂号排班"""
from fastapi import APIRouter, HTTPException, Query

from app.dao import db, hospital_dao

router = APIRouter(prefix="/api/hospitals", tags=["医院"])


@router.get("")
def list_hospitals(
    city: str | None = Query(default=None, description="城市：杭州/北京/上海/深圳"),
    district: str | None = Query(default=None, description="行政区"),
    department: str | None = Query(default=None, description="科室筛选"),
    lat: float | None = Query(default=None, ge=-90, le=90, description="用户定位纬度（提供后按真实距离排序）"),
    lng: float | None = Query(default=None, ge=-180, le=180, description="用户定位经度"),
):
    """查询医院列表（内置演示数据）。

    提供 lat/lng（浏览器定位）时按 haversine 真实距离升序（离我最近）；
    否则按市中心参考距离升序。返回 located 标记当前是否使用了真实定位。
    """
    located = lat is not None and lng is not None
    try:
        hospitals = hospital_dao.list_hospitals(city, district, department, lat, lng)
    except Exception:
        # MySQL 未启用时医院数据不存在，直接返回空（前端提示启用数据库）
        return {"hospitals": [], "located": False, "demo": True}
    districts = sorted({h["district"] for h in hospitals}) if hospitals else []
    return {"hospitals": hospitals, "districts": districts, "located": located, "demo": True}


@router.get("/schedule")
def get_schedule(
    hospital_id: int = Query(..., description="医院 id"),
    department: str = Query(..., description="科室"),
):
    """未来 7 天挂号排班（余号确定性生成，演示用）"""
    hospital = hospital_dao.get_hospital(hospital_id)
    if hospital is None:
        raise HTTPException(status_code=404, detail="医院不存在")
    if department not in hospital["departments"]:
        raise HTTPException(status_code=400, detail=f"该医院未开设「{department}」")
    return hospital_dao.get_schedule(hospital_id, department)
