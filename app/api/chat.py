"""对话接口：POST /api/chat，SSE 流式返回大模型输出"""
import json
import logging
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import iterate_in_threadpool

from app.config import settings
from app.service.chat_service import chat_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["对话"])


class HistoryMessage(BaseModel):
    """单条历史消息：只允许 user / assistant 两种角色，防止客户端注入 system 提示词"""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=settings.MAX_MESSAGE_LENGTH)


class ChatRequest(BaseModel):
    """聊天请求体"""

    message: str = Field(
        ..., min_length=1, max_length=settings.MAX_MESSAGE_LENGTH, description="用户输入内容"
    )
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=settings.MAX_HISTORY_MESSAGES,
        description="历史对话，user / assistant 交替",
    )


@router.post("/chat")
async def chat(req: ChatRequest):
    """聊天接口：接收用户输入，流式返回大模型输出（SSE）"""

    async def generate():
        # 大模型调用放在线程池中执行，避免阻塞事件循环
        stream = iterate_in_threadpool(
            chat_stream(req.message, [m.model_dump() for m in req.history])
        )
        try:
            async for text in stream:
                yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
            else:
                yield "data: [DONE]\n\n"
        except Exception:
            # 详细错误记入服务端日志，前端只返回友好提示，避免泄露底层细节
            logger.exception("聊天接口调用失败")
            yield f"data: {json.dumps({'error': '服务暂时不可用，请稍后重试'}, ensure_ascii=False)}\n\n"
        finally:
            # 无论正常结束还是中断，都主动关闭迭代器，触发底层连接释放
            await stream.aclose()

    return StreamingResponse(generate(), media_type="text/event-stream")
