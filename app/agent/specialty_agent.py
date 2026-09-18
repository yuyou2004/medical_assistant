"""专科 Agent：根据问题进行专业方向分析（第五阶段）"""
from app.agent.base import BaseAgent
from app.config.prompt import SPECIALTY_AGENT_PROMPT


class SpecialtyAgent(BaseAgent):
    """专科 Agent

    负责：判断可能涉及的医学专业方向（心血管/呼吸/消化/神经/皮肤/眼科……），
    给出就诊科室的先后建议。
    """

    name = "specialty"
    description = "专科 Agent：根据问题进行专业方向分析"
    system_prompt = SPECIALTY_AGENT_PROMPT
