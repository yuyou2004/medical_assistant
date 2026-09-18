"""问诊 Agent：理解问题、信息收集、多轮追问（第五阶段）"""
import logging
from typing import Any

from app.agent.base import BaseAgent
from app.config.prompt import INQUIRY_AGENT_PROMPT
from app.service import llm_service

logger = logging.getLogger(__name__)


class InquiryAgent(BaseAgent):
    """问诊 Agent

    负责：理解用户问题、收集医疗信息、判断信息是否完整、生成追问问题。
    输出 JSON：{"info_complete": bool, "next_question": str|null, "collected": {...}, "summary": str}
    """

    name = "inquiry"
    description = "问诊 Agent：理解问题、信息收集、多轮追问"
    system_prompt = INQUIRY_AGENT_PROMPT

    def run(self, context: str) -> dict[str, Any]:
        """分析对话内容，返回信息收集结果

        Args:
            context: 对话历史 + 用户最新输入（由调用方组装）
        """
        logger.info("Agent [%s] 开始执行", self.name)
        try:
            return llm_service.chat_json(self.build_messages(context))
        except Exception:
            # JSON 解析多次失败时兜底：视为信息不完整，发起通用追问，不让流程中断
            logger.exception("问诊 Agent 结构化输出失败，使用兜底追问")
            return {
                "info_complete": False,
                "next_question": "可以再详细描述一下你的症状吗？比如从什么时候开始、具体是什么感觉？",
                "collected": {},
                "summary": "信息收集失败",
            }
