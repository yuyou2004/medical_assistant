"""医院数据访问（M8 扩展）：医院查询 + 挂号排班生成

说明：医院为内置演示数据（无真实医院系统对接）；排班表按日期+医生+时段
确定性生成（同一条件永远得到相同余号），保证演示过程可复现。
医院带真实经纬度：用户提供定位时按 haversine 计算真实直线距离并排序
（"离我最近"），未定位时退回 distance_km 参考距离（市中心估算值）。
"""
import hashlib
import json
import math
from datetime import date, timedelta

from app.dao import db

# 各科室演示医生池（姓名、职称）
DOCTORS: dict[str, list[tuple[str, str]]] = {
    "皮肤科": [("王慧", "主任医师"), ("李明", "副主任医师"), ("张丽", "主治医师")],
    "内科": [("陈志强", "主任医师"), ("刘芳", "副主任医师"), ("赵伟", "主治医师")],
    "外科": [("周建国", "主任医师"), ("吴敏", "副主任医师"), ("郑涛", "主治医师")],
    "儿科": [("孙静", "主任医师"), ("钱多多", "副主任医师")],
    "妇产科": [("何秀兰", "主任医师"), ("林晓梅", "副主任医师")],
    "骨科": [("高翔", "主任医师"), ("许磊", "副主任医师"), ("邓超", "主治医师")],
    "眼科": [("黄丽华", "主任医师"), ("冯倩", "副主任医师")],
    "口腔科": [("宋佳", "主任医师"), ("徐斌", "主治医师")],
    "耳鼻喉科": [("蔡国庆", "主任医师"), ("马晓东", "副主任医师")],
    "中医科": [("陆仁", "主任医师"), ("蒋文", "副主任医师"), ("沈月", "主治医师")],
}

TIME_SLOTS = ["08:00-10:00", "10:00-12:00", "14:00-16:00", "16:00-17:30"]
SCHEDULE_DAYS = 7  # 排班展示未来 7 天


def _remaining(doctor: str, visit_date: str, slot: str, department: str) -> int:
    """确定性余号：同一条件结果固定，范围 0-10"""
    h = hashlib.md5(f"{doctor}|{visit_date}|{slot}|{department}".encode()).hexdigest()
    return int(h[:4], 16) % 11


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两点球面距离（公里）。地球半径取 6371km，医院间距量级下误差可忽略"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


_HOSPITAL_COLS = (
    "SELECT id, name, level, city, district, address, phone, departments, "
    "distance_km, rating, lat, lng FROM hospitals"
)


def list_hospitals(city: str | None = None, district: str | None = None,
                   department: str | None = None,
                   lat: float | None = None, lng: float | None = None) -> list[dict]:
    """按城市/区/科室筛选医院

    lat/lng 提供（用户真实定位）时：距离按 haversine 计算并按真实距离升序（离我最近）；
    未提供时：退回 distance_km 参考距离升序。返回的 distance_km 即当前使用的距离。
    """
    located = lat is not None and lng is not None
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_HOSPITAL_COLS + " ORDER BY distance_km")
            rows = cur.fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        depts = json.loads(r[7] or "[]")
        if city and r[3] != city:
            continue
        if district and r[4] != district:
            continue
        if department and department not in depts:
            continue
        r_lat, r_lng = float(r[10]) if r[10] is not None else None, float(r[11]) if r[11] is not None else None
        if located and r_lat is not None:
            distance = haversine_km(lat, lng, r_lat, r_lng)
        else:
            distance = float(r[8])
        result.append({
            "id": r[0], "name": r[1], "level": r[2], "city": r[3],
            "district": r[4], "address": r[5], "phone": r[6],
            "departments": depts, "distance_km": distance, "rating": float(r[9]),
            "lat": r_lat, "lng": r_lng,
        })
    if located:
        result.sort(key=lambda h: h["distance_km"])
    return result


def get_hospital(hospital_id: int) -> dict | None:
    """按 id 查医院（预约挂号时校验）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_HOSPITAL_COLS + " WHERE id=%s", (hospital_id,))
            r = cur.fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return {
        "id": r[0], "name": r[1], "level": r[2], "city": r[3],
        "district": r[4], "address": r[5], "phone": r[6],
        "departments": json.loads(r[7] or "[]"), "distance_km": float(r[8]), "rating": float(r[9]),
        "lat": float(r[10]) if r[10] is not None else None,
        "lng": float(r[11]) if r[11] is not None else None,
    }


def get_schedule(hospital_id: int, department: str) -> dict:
    """生成未来 7 天排班：dates / doctors / slots（余号确定性生成）"""
    doctors = DOCTORS.get(department, DOCTORS["内科"])
    today = date.today()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(SCHEDULE_DAYS)]
    slots: dict[str, dict[str, dict[str, int]]] = {}
    for d in dates:
        day: dict[str, dict[str, int]] = {}
        for slot in TIME_SLOTS:
            day[slot] = {name: _remaining(name, d, slot, department) for name, _ in doctors}
        slots[d] = day
    return {
        "hospital_id": hospital_id,
        "department": department,
        "dates": dates,
        "time_slots": TIME_SLOTS,
        "doctors": [{"name": n, "title": t} for n, t in doctors],
        "slots": slots,  # {date: {slot: {doctor: 余号}}}
    }
