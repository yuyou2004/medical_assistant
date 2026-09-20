"""用药提醒 DAO（M9 扩展）：用药计划的增删改查 + 每日服药打卡

说明：提醒触达由前端完成——页面打开时按计划中的服药时间点用浏览器
Notification 弹通知（本机演示方案；生产环境应换 Redis 定时任务 + 推送渠道）。
后端负责存储计划与打卡记录，并生成"今日待服药清单"。
"""
import json
from datetime import date

from app.dao import db


def _row_to_med(row) -> dict:
    try:
        time_points = json.loads(row[4] or "[]")
        if not isinstance(time_points, list):
            time_points = []
    except Exception:
        time_points = []
    return {
        "id": row[0], "medicine_name": row[2], "times_per_day": row[3],
        "time_points": time_points, "note": row[5] or "", "active": bool(row[6]),
    }


def list_medications(username: str) -> list[dict]:
    """我的用药计划（活跃在前）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, medicine_name, times_per_day, time_points, note, active "
                "FROM medications WHERE username=%s ORDER BY active DESC, id",
                (username,),
            )
            return [_row_to_med(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_medication(username: str, med_id: int) -> dict | None:
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, medicine_name, times_per_day, time_points, note, active "
                "FROM medications WHERE username=%s AND id=%s",
                (username, med_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_med(row) if row else None


def create_medication(username: str, medicine_name: str, times_per_day: int,
                      time_points: list[str], note: str = "") -> int:
    """新增用药计划，返回 id"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO medications (username, medicine_name, times_per_day, time_points, note) "
                "VALUES (%s,%s,%s,%s,%s)",
                (username, medicine_name, times_per_day, json.dumps(time_points, ensure_ascii=False), note),
            )
            return cur.lastrowid
    finally:
        conn.close()


def update_medication(username: str, med_id: int, **fields) -> bool:
    """更新计划字段（medicine_name / times_per_day / time_points / note / active）"""
    allowed = {"medicine_name", "times_per_day", "time_points", "note", "active"}
    sets, values = [], []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "time_points":
            value = json.dumps(value, ensure_ascii=False)
        sets.append(f"{key}=%s")
        values.append(value)
    if not sets:
        return False
    values += [username, med_id]
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE medications SET {', '.join(sets)} WHERE username=%s AND id=%s", values)
            return cur.rowcount > 0
    finally:
        conn.close()


def delete_medication(username: str, med_id: int) -> bool:
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM medications WHERE username=%s AND id=%s", (username, med_id))
            return cur.rowcount > 0
    finally:
        conn.close()


def take_log(username: str, med_id: int, time_point: str, log_date: str | None = None) -> bool:
    """服药打卡（同药同日期同时段只记一次）。打卡时段不在计划内时返回 False"""
    med = get_medication(username, med_id)
    if med is None or time_point not in med["time_points"]:
        return False
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO medication_logs (username, medication_id, log_date, time_point) "
                "VALUES (%s,%s,%s,%s)",
                (username, med_id, log_date or date.today().isoformat(), time_point),
            )
    finally:
        conn.close()
    return True


def today_checklist(username: str) -> dict:
    """今日服药清单：计划 × 时段 → 是否已打卡"""
    today = date.today().isoformat()
    meds = [m for m in list_medications(username) if m["active"]]
    if not meds:
        return {"date": today, "items": [], "taken": 0, "total": 0}
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            med_ids = ",".join(str(m["id"]) for m in meds)
            cur.execute(
                f"SELECT medication_id, time_point FROM medication_logs "
                f"WHERE username=%s AND log_date=%s AND medication_id IN ({med_ids})",
                (username, today),
            )
            logged = {(r[0], r[1]) for r in cur.fetchall()}
    finally:
        conn.close()
    items = []
    for m in meds:
        for tp in sorted(m["time_points"]):
            items.append({
                "medication_id": m["id"],
                "medicine_name": m["medicine_name"],
                "time_point": tp,
                "taken": (m["id"], tp) in logged,
            })
    taken = sum(1 for it in items if it["taken"])
    return {"date": today, "items": items, "taken": taken, "total": len(items)}
