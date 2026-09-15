"""项目入口：FastAPI 应用"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat
from app.config import settings

app = FastAPI(title="AI 医疗咨询助手", version="0.1.0")

# 跨域配置（前端联调需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router)


@app.get("/")
def root():
    return {"message": "AI 医疗咨询助手服务已启动"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True
    )
