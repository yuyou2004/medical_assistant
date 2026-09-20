"""健康数据趋势 DAO（M9 扩展）：体重/血压等自测记录的写入与查询

说明：记录按用户隔离；前端以折线图展示趋势（纯前端渲染，后端只提供数据）。
"""
from datetime import date

from app.dao import db

# 支持的记录类型（数值型指标，前端折线图 X 轴为日期）
RECORD_TYPES = {"weight": "体重(kg)", "systolic": "收缩压(mmHg)", "diastolic": "舒张压(mmHg)"}

# 同一日期同类型只保留一条：插入时覆盖（避免误点重复记录）
_UPSERT_SQL = (
    "INSERT INTO health_records (username, record_type, value, note, record_date) "
    "VALUES (%s,%s,%s,%s,%s) "
    "ON DUPLICATE KEY UPDATE value=VALUES(value), note=VALUES(note) "
)


def add_record(username: str, record_type: str, value: float, note: str = "",
               record_date: str | None = None) -> None:
    """写入一条健康记录（同用户同日期同类型覆盖旧值）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_UPSERT_SQL, (username, record_type, value, note, record_date or date.today().isoformat()))
    finally:
        conn.close()


def list_records(username: str, record_type: str, days: int = 30) -> list[dict]:
    """查询某类型最近 N 天记录，按日期升序（供折线图使用）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, record_type, value, note, record_date FROM health_records "
                "WHERE username=%s AND record_type=%s "
                "AND record_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "ORDER BY record_date",
                (username, record_type, days),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"id": r[0], "record_type": r[1], "value": float(r[2]), "note": r[3], "record_date": str(r[4])}
        for r in rows
    ]


def delete_record(username: str, record_id: int) -> bool:
    """删除一条记录，返回是否删除成功"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM health_records WHERE id=%s AND username=%s", (record_id, username))
            return cur.rowcount > 0
    finally:
        conn.close()


def latest_values(username: str) -> dict:
    """各类指标最新一条（首页健康卡片展示）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            latest = {}
            for record_type in RECORD_TYPES:
                cur.execute(
                    "SELECT value, record_date FROM health_records "
                    "WHERE username=%s AND record_type=%s ORDER BY record_date DESC LIMIT 1",
                    (username, record_type),
                )
                row = cur.fetchone()
                if row:
                    latest[record_type] = {"value": float(row[0]), "record_date": str(row[1])}
            return latest
    finally:
        conn.close()
