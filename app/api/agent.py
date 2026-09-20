"""智能体接口：POST /api/agent/chat，由 Supervisor 总控，SSE 流式返回过程事件与最终回答"""
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.concurrency import iterate_in_threadpool

from app.agent import get_agent
from app.api.auth import _extract_token, check_token
from app.api.chat import HistoryMessage  # 复用聊天接口的历史消息校验
from app.config import settings
from app.dao import profile_dao

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["智能体"])


class AgentChatRequest(BaseModel):
    """智能体咨询请求体"""

    message: str = Field(
        ..., min_length=1, max_length=settings.MAX_MESSAGE_LENGTH, description="用户输入内容"
    )
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=settings.MAX_HISTORY_MESSAGES,
        description="历史对话，user / assistant 交替",
    )
    include_profile: bool = Field(
        default=False, description="是否携带用户健康档案参与会诊（需登录且已填档案）"
    )


@router.post("/chat")
async def agent_chat(req: AgentChatRequest, request: Request):
    """智能体咨询接口：SSE 事件流

    事件类型：plan（路由计划）/ agent（子 Agent 结果）/ content（最终回答片段）/
    done（结束）/ error（错误）
    """

    async def generate():
        supervisor = get_agent("supervisor")
        if supervisor is None:
            yield f"data: {json.dumps({'type': 'error', 'data': 'Supervisor 未初始化'}, ensure_ascii=False)}\n\n"
            return
        # 可选：携带健康档案（会诊时自动附加到本轮输入，前端展示的消息保持原文）
        user_input = req.message
        if req.include_profile:
            username = check_token(_extract_token(request.headers.get("authorization")))
            if username:
                try:
                    profile_text = profile_dao.format_profile(profile_dao.get_profile(username))
                    if profile_text:
                        user_input = req.message + "\n\n[用户健康档案（会诊时自动携带）]\n" + profile_text
                except Exception:
                    logger.warning("健康档案读取失败，本次会诊不携带档案")
        # 大模型调用放在线程池中执行，避免阻塞事件循环
        stream = iterate_in_threadpool(
            supervisor.orchestrate(user_input, [m.model_dump() for m in req.history])
        )
        try:
            async for event in stream:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception:
            # 详细错误记入服务端日志，前端只返回友好提示
            logger.exception("智能体调用失败")
            yield f"data: {json.dumps({'type': 'error', 'data': '服务暂时不可用，请稍后重试'}, ensure_ascii=False)}\n\n"
        finally:
            # 无论正常结束还是中断，都主动关闭迭代器，触发底层连接释放
            await stream.aclose()

    return StreamingResponse(generate(), media_type="text/event-stream")
