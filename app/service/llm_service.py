"""LLM 调用服务：统一封装大模型客户端，供聊天服务和各 Agent 复用"""
import json
import logging
import re
import time
from typing import Any, Iterator

import httpx
from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# 全局客户端（OpenAI 兼容接口，DeepSeek 直接可用）
# connect / read / write 超时分开设置，避免网络异常时长时间挂起
_client = OpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0),
)


def chat_stream(messages: list[dict], temperature: float | None = None) -> Iterator[str]:
    """流式对话：逐段返回模型生成的文本"""
    start = time.monotonic()
    logger.info("调用大模型开始：model=%s，消息 %d 条", settings.LLM_MODEL, len(messages))
    response = _client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
        stream=True,
    )
    try:
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    finally:
        # 无论正常结束还是中途中断，都关闭底层连接，避免资源泄漏
        response.close()
        logger.info("调用大模型结束，耗时 %.2f 秒", time.monotonic() - start)


def chat(messages: list[dict], temperature: float | None = None) -> str:
    """非流式对话：返回完整文本（Agent 之间传递结果用）"""
    response = _client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
        stream=False,
    )
    return response.choices[0].message.content or ""


def chat_json(messages: list[dict], temperature: float = 0) -> dict[str, Any]:
    """结构化对话：要求模型返回 JSON 并解析，解析失败自动重试一次

    Args:
        messages: 对话消息，最后一条应为用户消息
        temperature: 结构化输出用低温，保证格式稳定
    """
    for attempt in (1, 2):
        text = chat(messages, temperature=temperature)
        try:
            # 兼容模型把 JSON 包在 ```json ``` 代码块里的情况
            match = re.search(r"\{.*\}", text, re.S)
            return json.loads(match.group(0) if match else text)
        except json.JSONDecodeError:
            logger.warning("JSON 解析失败（第 %d 次），原文：%.200s", attempt, text)
            messages.append({"role": "assistant", "content": text})
            messages.append(
                {"role": "user", "content": "上一条输出不是合法 JSON，请重新只输出 JSON，不要包含任何其他文字。"}
            )
    raise RuntimeError("模型多次输出非法 JSON，结构化调用失败")
