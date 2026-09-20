"""预约挂号数据访问（M8 扩展）：创建 / 查询 / 取消"""
from app.dao import db
from app.dao import hospital_dao


def count_active(hospital_name: str, department: str, doctor: str,
                 visit_date: str, time_slot: str) -> int:
    """同医院同科室同医生同时段的已挂号数（用于余号校验）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM appointments WHERE hospital_name=%s AND department=%s "
                "AND doctor=%s AND visit_date=%s AND time_slot=%s AND status='active'",
                (hospital_name, department, doctor, visit_date, time_slot),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def create(username: str, hospital_name: str, department: str, doctor: str,
           visit_date: str, time_slot: str, patient_name: str, patient_phone: str,
           symptom: str) -> tuple[bool, int | str]:
    """创建预约，成功返回 (True, 预约号)；号源不足返回 (False, 提示)"""
    remaining = hospital_dao._remaining(doctor, visit_date, time_slot, department)
    taken = count_active(hospital_name, department, doctor, visit_date, time_slot)
    if taken >= remaining:
        return False, f"该时段号源已满（余 {remaining} 已约 {taken}），请选择其他时段"
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO appointments "
                "(username, hospital_name, department, doctor, visit_date, time_slot, "
                " patient_name, patient_phone, symptom) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (username, hospital_name, department, doctor, visit_date, time_slot,
                 patient_name, patient_phone, symptom),
            )
            return True, cur.lastrowid
    finally:
        conn.close()


def list_by_user(username: str) -> list[dict]:
    """某用户全部预约（按预约时间倒序，取消的置后）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, hospital_name, department, doctor, visit_date, time_slot, "
                "patient_name, patient_phone, symptom, status, created_at "
                "FROM appointments WHERE username=%s "
                "ORDER BY status='active' DESC, visit_date DESC, id DESC",
                (username,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "id": r[0], "hospital_name": r[1], "department": r[2], "doctor": r[3],
            "visit_date": str(r[4]), "time_slot": r[5], "patient_name": r[6],
            "patient_phone": r[7], "symptom": r[8], "status": r[9],
            "created_at": str(r[10]),
        }
        for r in rows
    ]


def cancel(appointment_id: int, username: str) -> bool:
    """取消预约（只能取消自己的、且未取消的），成功返回 True"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE appointments SET status='cancelled' "
                "WHERE id=%s AND username=%s AND status='active'",
                (appointment_id, username),
            )
            return cur.rowcount > 0
    finally:
        conn.close()
