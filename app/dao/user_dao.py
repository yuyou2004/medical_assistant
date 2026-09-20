"""用户数据访问（第二阶段，MySQL）"""
import hashlib
import logging
import secrets

import pymysql

from app.dao import db

logger = logging.getLogger(__name__)

_PBKDF2_ITERATIONS = 100_000  # 口令哈希迭代次数（stdlib 实现，无额外依赖）


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS
    ).hex()


def create_user(username: str, password: str) -> tuple[bool, str]:
    """注册用户，返回 (是否成功, 提示信息)"""
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (%s, %s, %s)",
                (username, pw_hash, salt),
            )
        conn.close()
        return True, "注册成功"
    except pymysql.err.IntegrityError:
        return False, "该账号已存在"
    except Exception:
        logger.exception("用户注册失败")
        return False, "注册失败，请稍后重试"


def verify_user(username: str, password: str) -> bool:
    """校验用户名密码，正确返回 True"""
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash, salt FROM users WHERE username = %s", (username,)
            )
            row = cur.fetchone()
        conn.close()
        if row is None:
            return False
        return _hash_password(password, row[1]) == row[0]
    except Exception:
        logger.exception("用户校验失败")
        return False


def get_user(username: str) -> dict | None:
    """读取用户基础信息（用户名 + 注册时间），不存在返回 None"""
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, created_at FROM users WHERE username = %s", (username,)
            )
            row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        created_at = row[1].strftime("%Y-%m-%d") if row[1] else None
        return {"username": row[0], "created_at": created_at}
    except Exception:
        logger.exception("读取用户信息失败")
        return None


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """修改密码：校验旧密码后重新加盐哈希写入，返回 (是否成功, 提示信息)"""
    if not verify_user(username, old_password):
        return False, "旧密码不正确"
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(new_password, salt)
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s, salt=%s WHERE username=%s",
                (pw_hash, salt, username),
            )
        conn.close()
        return True, "密码修改成功"
    except Exception:
        logger.exception("修改密码失败")
        return False, "修改失败，请稍后重试"
