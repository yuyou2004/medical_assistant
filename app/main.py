"""项目入口：FastAPI 应用"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent import setup_default_agents
from app.api import agent, auth, chat, consultation, knowledge
from app.config import settings
from app.dao import db

# 统一日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动 / 关闭时执行"""
    setup_default_agents()  # 注册已实现的 Agent
    db.init_db()  # MySQL 建库建表（未启用或不可用时自动回退内存存储）
    if settings.LLM_CONFIGURED:
        logger.info("大模型已配置：%s（%s）", settings.LLM_MODEL, settings.LLM_BASE_URL)
    else:
        logger.warning("未配置 DEEPSEEK_API_KEY，聊天接口将不可用，请在 .env 文件中填写")
    yield


app = FastAPI(title="AI 医疗咨询助手", version="0.1.0", lifespan=lifespan)

# 跨域配置（前端联调需要，上线前应收紧 allow_origins）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(consultation.router)
app.include_router(knowledge.router)


@app.get("/")
def root():
    return {"message": "AI 医疗咨询助手服务已启动"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True
    )
