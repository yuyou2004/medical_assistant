"""问诊业务服务（第四阶段）：会话与历史记录管理

存储策略（M7 系统整合后）：
- MYSQL_ENABLED=1 时消息持久化到 MySQL（重启不丢），内存仍记录会话活跃状态；
- 未启用或数据库不可用时，退回内存存储（重启丢失，已有行为）。
为防内存无限增长：会话有 TTL（过期清理）和数量上限（超出淘汰最旧的）。
"""
import logging
import threading
import time
from uuid import uuid4

from app.config import settings
from app.dao import consultation_dao

logger = logging.getLogger(__name__)

MAX_SESSIONS = 100  # 最多保留的会话数
SESSION_TTL_SECONDS = 24 * 3600  # 会话空闲 24 小时视为过期

# session_id -> {"messages": [{"role", "content"}], "created_at": ts, "last_active": ts}
_sessions: dict[str, dict] = {}
_lock = threading.Lock()


def _evict_locked() -> None:
    """清理过期会话；数量超上限时按最久未活跃淘汰"""
    now = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if now - s["last_active"] > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _sessions[sid]
    while len(_sessions) > MAX_SESSIONS:
        oldest = min(_sessions, key=lambda s: _sessions[s]["last_active"])
        del _sessions[oldest]
    if expired:
        logger.info("清理会话 %d 个，剩余 %d 个", len(expired), len(_sessions))


def create_session() -> str:
    """创建新会话，返回 session_id"""
    session_id = uuid4().hex
    now = time.time()
    with _lock:
        _evict_locked()
        _sessions[session_id] = {"messages": [], "created_at": now, "last_active": now}
    logger.info("创建会话：%s", session_id)
    return session_id


def get_or_create_session(session_id: str | None) -> str:
    """获取会话；不存在或未提供时新建"""
    if session_id and session_id in _sessions:
        return session_id
    return create_session()


def get_history(session_id: str) -> list[dict] | None:
    """返回会话的历史消息（role/content），会话不存在时返回 None

    启用 MySQL 后优先读库（服务重启后内存为空，历史从库中恢复）；
    库不可用或未启用时退回内存。
    """
    if settings.DB_ENABLED:
        try:
            db_history = consultation_dao.load_messages(session_id)
            if db_history is not None or session_id not in _sessions:
                # 库里有记录，或内存里也没有该会话（重启后的老会话）→ 以库为准
                return db_history
        except Exception:
            logger.exception("MySQL 读取失败，回退内存存储")
    session = _sessions.get(session_id)
    if session is None:
        return None
    return list(session["messages"])


def append_message(session_id: str, role: str, content: str) -> None:
    """往会话追加一条消息（启用 MySQL 时同时持久化）"""
    session = _sessions.get(session_id)
    if session is None:
        logger.warning("会话不存在，忽略追加：%s", session_id)
        return
    session["messages"].append({"role": role, "content": content})
    session["last_active"] = time.time()
    if settings.DB_ENABLED:
        try:
            consultation_dao.save_message(session_id, role, content)
        except Exception:
            logger.exception("MySQL 写入失败，仅保留内存记录")


def list_sessions() -> list[dict]:
    """列出所有会话概要（按创建时间倒序）；启用 MySQL 时以库为准"""
    if settings.DB_ENABLED:
        try:
            return consultation_dao.list_sessions()
        except Exception:
            logger.exception("MySQL 列表读取失败，回退内存存储")
    return [
        {
            "session_id": sid,
            "created_at": s["created_at"],
            "message_count": len(s["messages"]),
            "first_message": s["messages"][0]["content"][:50] if s["messages"] else "",
        }
        for sid, s in sorted(
            _sessions.items(), key=lambda kv: kv[1]["created_at"], reverse=True
        )
    ]
