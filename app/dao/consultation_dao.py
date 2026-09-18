"""问诊记录数据访问（第七阶段：系统整合）：会话消息持久化到 MySQL"""
import logging

from app.dao import db

logger = logging.getLogger(__name__)


def save_message(session_id: str, role: str, content: str) -> None:
    """保存一条会话消息"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO consultations (session_id, role, content) VALUES (%s, %s, %s)",
                (session_id, role, content),
            )
    finally:
        conn.close()


def load_messages(session_id: str) -> list[dict] | None:
    """读取会话全部消息（按时间顺序）；会话无记录时返回 None"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM consultations WHERE session_id = %s ORDER BY id",
                (session_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        return None
    return [{"role": r[0], "content": r[1]} for r in rows]


def list_sessions() -> list[dict]:
    """列出最近 100 个会话概要（按最新创建时间倒序）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT session_id, MIN(created_at), COUNT(*)
                   FROM consultations GROUP BY session_id
                   ORDER BY MIN(id) DESC LIMIT 100"""
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    result = []
    for sid, created_at, count in rows:
        first_message = ""
        try:
            conn = db.get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content FROM consultations WHERE session_id = %s ORDER BY id LIMIT 1",
                    (sid,),
                )
                row = cur.fetchone()
            conn.close()
            if row:
                first_message = row[0][:50]
        except Exception:
            logger.exception("读取会话首条消息失败")
        result.append(
            {
                "session_id": sid,
                "created_at": created_at.timestamp() if created_at else 0,
                "message_count": count,
                "first_message": first_message,
            }
        )
    return result
