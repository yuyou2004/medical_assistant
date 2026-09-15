"""对话接口：POST /api/chat，SSE 流式返回大模型输出"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.service.chat_service import chat_stream

router = APIRouter(prefix="/api", tags=["对话"])


class ChatRequest(BaseModel):
    """聊天请求体"""

    message: str = Field(..., description="用户输入内容")
    history: list[dict] = Field(
        default_factory=list, description="历史对话，user / assistant 交替"
    )


@router.post("/chat")
def chat(req: ChatRequest):
    """聊天接口：接收用户输入，流式返回大模型输出（SSE）"""

    def generate():
        try:
            for text in chat_stream(req.message, req.history):
                yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:  # 调用失败时也以 SSE 返回，前端可以展示错误
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
