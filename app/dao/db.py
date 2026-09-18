"""数据库连接与初始化（M7 系统整合）：pymysql 直连 MySQL，简单可靠"""
import logging

import pymysql

from app.config import settings

logger = logging.getLogger(__name__)


def _connect(database: str | None) -> pymysql.connections.Connection:
    """新建数据库连接（调用方用完需 close）"""
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=database,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=5,
    )


def get_connection() -> pymysql.connections.Connection:
    """连接到业务库"""
    return _connect(settings.MYSQL_DB)


def init_db() -> bool:
    """建库建表（幂等），成功返回 True；数据库不可用时返回 False 并记日志"""
    if not settings.DB_ENABLED:
        logger.info("MYSQL_ENABLED 未开启，使用内存存储")
        return False
    try:
        # 先不带 database 连接，确保库存在
        conn = _connect(None)
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DB}` "
                "DEFAULT CHARACTER SET utf8mb4"
            )
        conn.close()

        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(128) NOT NULL,
                    salt VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS consultations (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    role VARCHAR(16) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_session (session_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
        conn.close()
        logger.info(
            "MySQL 初始化完成：%s@%s:%s/%s",
            settings.MYSQL_USER, settings.MYSQL_HOST, settings.MYSQL_PORT, settings.MYSQL_DB,
        )
        return True
    except Exception:
        logger.exception("MySQL 初始化失败，回退内存存储")
        return False
