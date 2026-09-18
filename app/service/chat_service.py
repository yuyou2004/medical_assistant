"""聊天服务：组装聊天消息并调用大模型流式输出"""
from typing import Iterator

from app.config import settings
from app.config.prompt import MEDICAL_ASSISTANT_PROMPT
from app.service.llm_service import chat_stream as _llm_stream


def chat_stream(user_message: str, history: list[dict] | None = None) -> Iterator[str]:
    """调用大模型聊天，逐段流式返回生成的文本

    Args:
        user_message: 用户本次输入的内容
        history: 历史对话，只包含 user / assistant 两种角色的消息
    """
    # 只保留最近 N 条历史，避免长对话 token 无限增长
    if history:
        history = history[-settings.MAX_HISTORY_MESSAGES:]

    messages = [{"role": "system", "content": MEDICAL_ASSISTANT_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    yield from _llm_stream(messages)
