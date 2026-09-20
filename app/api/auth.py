"""用户认证接口（第二阶段：基础系统搭建）：注册 / 登录"""
import logging
import secrets
import threading
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.dao import user_dao

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["认证"])

# 登录令牌存储（内存版）：token -> {"username": ..., "expires_at": ...}
# 说明：令牌存内存意味着服务重启后需重新登录；后续可换 Redis（docker-compose 已备）
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 令牌有效期 7 天
_tokens: dict[str, dict] = {}
_tokens_lock = threading.Lock()


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=20, pattern=r"^[\w一-龥]+$")
    password: str = Field(..., min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=1, max_length=64)


def _require_db() -> None:
    """认证依赖 MySQL（用户表在库里），未启用时直接拒绝"""
    if not settings.DB_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="用户系统未启用：请启动 MySQL 并设置 MYSQL_ENABLED=1 后重启服务",
        )


@router.post("/register")
def register(req: RegisterRequest) -> dict:
    """注册新用户（密码经 PBKDF2 加盐哈希后入库）"""
    _require_db()
    ok, msg = user_dao.create_user(req.username, req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    logger.info("新用户注册：%s", req.username)
    return {"message": msg}


@router.post("/login")
def login(req: LoginRequest) -> dict:
    """登录，成功返回访问令牌"""
    _require_db()
    if not user_dao.verify_user(req.username, req.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = secrets.token_hex(32)
    with _tokens_lock:
        _tokens[token] = {
            "username": req.username,
            "expires_at": time.time() + TOKEN_TTL_SECONDS,
        }
    logger.info("用户登录：%s", req.username)
    return {"token": token, "username": req.username, "expires_in": TOKEN_TTL_SECONDS}


def check_token(token: str | None) -> str | None:
    """校验令牌，返回用户名；无效/过期返回 None（供后续需要登录的接口使用）"""
    if not token:
        return None
    with _tokens_lock:
        info = _tokens.get(token)
    if info and info["expires_at"] > time.time():
        return info["username"]
    return None


def _extract_token(authorization: str | None) -> str | None:
    """从 Authorization 头解析 Bearer 令牌"""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    """FastAPI 依赖：校验 Bearer 令牌，返回当前用户名（未登录抛 401）"""
    username = check_token(_extract_token(authorization))
    if username is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return username


@router.get("/me")
def me(username: str = Depends(get_current_user)) -> dict:
    """当前登录用户信息（前端首屏用于校验本地令牌是否有效）"""
    return {"username": username}


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    """退出登录：吊销令牌（服务重启后令牌本身也会失效）"""
    token = _extract_token(authorization)
    if token:
        with _tokens_lock:
            _tokens.pop(token, None)
    return {"message": "已退出登录"}
