"""聊天服务：调用大模型，支持流式输出"""
from typing import Iterator

from openai import OpenAI

from app.config import settings
from app.config.prompt import MEDICAL_ASSISTANT_PROMPT

# 全局客户端（OpenAI 兼容接口，DeepSeek 直接可用）
_client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL, timeout=60)


def chat_stream(user_message: str, history: list[dict] | None = None) -> Iterator[str]:
    """调用大模型聊天，逐段流式返回生成的文本

    Args:
        user_message: 用户本次输入的内容
        history: 历史对话，只包含 user / assistant 两条角色交替的消息
    """
    messages = [{"role": "system", "content": MEDICAL_ASSISTANT_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = _client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        stream=True,
    )
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
