"""风险评估 Agent：风险因素和危险信号识别（第五阶段）"""
import logging
from typing import Any

from app.agent.base import BaseAgent
from app.config.prompt import RISK_AGENT_PROMPT
from app.service import llm_service

logger = logging.getLogger(__name__)

# 危险信号关键词（硬规则兜底，不依赖大模型判断，实现文档 5.10 高风险症状识别）
# 命中任一关键词直接判高风险，提示立即就医
RED_FLAG_KEYWORDS = [
    "剧烈胸痛", "胸口剧痛", "胸痛剧烈", "呼吸困难", "喘不上气", "憋气",
    "意识不清", "昏迷", "晕厥", "抽搐",
    "大出血", "吐血", "咳血", "便血", "口角歪斜", "肢体无力",
    "剧烈头痛", "剧烈腹痛", "窒息", "高烧不退",
]


class RiskAgent(BaseAgent):
    """风险评估 Agent

    负责：风险因素分析、危险信号识别、风险等级判断（低/中/高）、就医建议。
    输出 JSON：{"risk_level": str, "danger_signals": [...], "analysis": str, "advice": str}

    两层防护：
    1. 硬规则：命中危险信号关键词直接判高风险（快速、可靠，不受模型判断波动影响）
    2. 大模型：无关键词命中时由 LLM 按 RISK_AGENT_PROMPT 结构化评估
    """

    name = "risk"
    description = "风险评估 Agent：风险因素和危险信号识别"
    system_prompt = RISK_AGENT_PROMPT

    @staticmethod
    def check_red_flags(text: str) -> list[str]:
        """在文本中查找危险信号关键词，返回命中的关键词列表"""
        return [kw for kw in RED_FLAG_KEYWORDS if kw in text]

    def run(self, context: str) -> dict[str, Any]:
        logger.info("Agent [%s] 开始执行", self.name)

        # 硬规则兜底：命中危险信号直接判高风险，省一次 LLM 调用且结论可靠
        flags = self.check_red_flags(context)
        if flags:
            logger.warning("命中危险信号：%s", "、".join(flags))
            return {
                "risk_level": "高风险",
                "danger_signals": flags,
                "analysis": f"发现危险信号：{'、'.join(flags)}。这些表现可能与急重症相关，需要立即医疗干预。",
                "advice": "请立即就医或拨打急救电话，不要等待观察，也不要自行驾车。",
            }

        try:
            return llm_service.chat_json(self.build_messages(context))
        except Exception:
            # 结构化输出失败时兜底为文本结论，不让流程中断
            logger.exception("风险评估 Agent 结构化输出失败，使用兜底文本")
            return {
                "risk_level": "无法判断",
                "danger_signals": [],
                "analysis": "结构化分析失败，请根据症状信息谨慎评估",
                "advice": "如症状明显或持续，建议咨询医生",
            }
