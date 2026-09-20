"""医院数据访问（M8 扩展）：医院查询 + 挂号排班生成

说明：医院为内置演示数据（无真实医院系统对接）；排班表按日期+医生+时段
确定性生成（同一条件永远得到相同余号），保证演示过程可复现。
"""
import hashlib
import json
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


def list_hospitals(city: str | None = None, district: str | None = None,
                   department: str | None = None) -> list[dict]:
    """按城市/区/科室筛选医院，返回距离升序"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, level, city, district, address, phone, departments, distance_km, rating FROM hospitals ORDER BY distance_km")
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
        result.append({
            "id": r[0], "name": r[1], "level": r[2], "city": r[3],
            "district": r[4], "address": r[5], "phone": r[6],
            "departments": depts, "distance_km": float(r[8]), "rating": float(r[9]),
        })
    return result


def get_hospital(hospital_id: int) -> dict | None:
    """按 id 查医院（预约挂号时校验）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, level, city, district, address, phone, departments, distance_km, rating FROM hospitals WHERE id=%s", (hospital_id,))
            r = cur.fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return {
        "id": r[0], "name": r[1], "level": r[2], "city": r[3],
        "district": r[4], "address": r[5], "phone": r[6],
        "departments": json.loads(r[7] or "[]"), "distance_km": float(r[8]), "rating": float(r[9]),
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
