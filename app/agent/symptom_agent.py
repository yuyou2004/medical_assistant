"""症状分析 Agent：症状提取、整理和初步分析（第五阶段）"""
from app.agent.base import BaseAgent
from app.config.prompt import SYMPTOM_AGENT_PROMPT


class SymptomAgent(BaseAgent):
    """症状分析 Agent

    负责：症状提取、症状整理、症状关系分析、初步分析（可能的疾病方向）。
    """

    name = "symptom"
    description = "症状分析 Agent：症状提取、整理和初步分析"
    system_prompt = SYMPTOM_AGENT_PROMPT
