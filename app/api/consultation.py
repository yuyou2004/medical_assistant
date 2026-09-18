"""问诊接口（第四阶段）：POST /api/consultation 多智能体会诊（SSE 事件流）+ 会话历史查询"""
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import iterate_in_threadpool

from app.agent import get_agent
from app.config import settings
from app.service import consultation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["问诊"])


class ConsultationRequest(BaseModel):
    """问诊请求体：session_id 为空时自动创建新会话"""

    message: str = Field(..., min_length=1, max_length=settings.MAX_MESSAGE_LENGTH, description="用户输入内容")
    session_id: str | None = Field(default=None, max_length=64, description="会话 ID，多轮问诊需携带同一个")


@router.post("/consultation")
async def consultation(req: ConsultationRequest):
    """多智能体会诊接口：SSE 事件流

    会话历史由服务端按 session_id 维护，多轮问诊只需携带同一个 session_id。
    事件类型：session（会话 ID）/ plan（路由计划）/ agent（子 Agent 结果）/
    question（追问）/ content（最终回答片段）/ done（结束）/ error（错误）
    """

    async def generate():
        supervisor = get_agent("supervisor")
        if supervisor is None:
            yield f"data: {json.dumps({'type': 'error', 'data': 'Supervisor 未初始化'}, ensure_ascii=False)}\n\n"
            return
        session_id = consultation_service.get_or_create_session(req.session_id)
        history = consultation_service.get_history(session_id) or []
        yield f"data: {json.dumps({'type': 'session', 'data': {'session_id': session_id}}, ensure_ascii=False)}\n\n"

        # 收集本轮完整回复（追问内容或最终回答），结束后写入会话历史
        answer_parts: list[str] = []
        completed = False
        stream = iterate_in_threadpool(supervisor.orchestrate(req.message, history))
        try:
            async for event in stream:
                if event.get("type") in ("content", "question"):
                    answer_parts.append(event.get("data", ""))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            completed = True
        except Exception:
            logger.exception("问诊接口调用失败")
            yield f"data: {json.dumps({'type': 'error', 'data': '服务暂时不可用，请稍后重试'}, ensure_ascii=False)}\n\n"
        finally:
            # 放在 finally 里：即使客户端提前断开（GeneratorExit），
            # 用户消息也要写入历史，保证多轮问诊上下文不丢
            await stream.aclose()
            consultation_service.append_message(session_id, "user", req.message)
            if completed:  # 只有正常流完才存助手消息，避免存半截回答
                answer_text = "".join(answer_parts).strip()
                if answer_text:
                    consultation_service.append_message(session_id, "assistant", answer_text)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/history/{session_id}")
def get_history(session_id: str):
    """查询会话历史消息（对话历史功能）"""
    history = consultation_service.get_history(session_id)
    if history is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session_id": session_id, "messages": history}


@router.get("/sessions")
def list_sessions():
    """列出所有会话概要"""
    return {"sessions": consultation_service.list_sessions()}
