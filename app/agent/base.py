"""Agent 基类：所有具体 Agent 继承它，复用统一的 LLM 调用能力"""
import logging
from typing import Iterator

from app.service import llm_service

logger = logging.getLogger(__name__)


class BaseAgent:
    """Agent 基类

    子类只需要定义 name / description / system_prompt 三个属性：
    - name：注册表里的唯一标识，Supervisor 靠它路由
    - description：职责说明，给 Supervisor 判断"该找谁"用
    - system_prompt：该 Agent 的角色提示词
    """

    name: str = "base_agent"
    description: str = "基础 Agent"
    system_prompt: str = ""

    def build_messages(self, user_content: str, prompt_override: str | None = None) -> list[dict]:
        """组装消息：系统提示词 + 用户内容（上下文信息由调用方写进 user_content）

        prompt_override：临时替换系统提示词（如同一 Agent 的不同模式）。
        """
        return [
            {"role": "system", "content": prompt_override or self.system_prompt},
            {"role": "user", "content": user_content},
        ]

    def run(self, context: str, prompt_override: str | None = None) -> str:
        """执行 Agent 任务（非流式），返回结果文本，供其他 Agent 或 Supervisor 使用"""
        logger.info("Agent [%s] 开始执行", self.name)
        return llm_service.chat(self.build_messages(context, prompt_override))

    def run_stream(self, context: str, prompt_override: str | None = None) -> Iterator[str]:
        """执行 Agent 任务（流式），用于向用户实时展示过程"""
        yield from llm_service.chat_stream(self.build_messages(context, prompt_override))
