"""Agent 模块：Agent 注册表 + 各智能体实现"""
import logging

from app.agent.base import BaseAgent

logger = logging.getLogger(__name__)

# Agent 注册表：Supervisor 通过 name 路由到已实现的 Agent
# 后续实现新的 Agent 时，在 setup_default_agents 中 register 即可被 Supervisor 调度
_registry: dict[str, BaseAgent] = {}


def register(agent: BaseAgent) -> None:
    """把 Agent 加入注册表"""
    _registry[agent.name] = agent
    logger.info("已注册 Agent：%s —— %s", agent.name, agent.description)


def get_agent(name: str) -> BaseAgent | None:
    """按名称获取 Agent，未注册时返回 None"""
    return _registry.get(name)


def list_agents() -> dict[str, str]:
    """返回 {name: description}，供 Supervisor 路由参考"""
    return {name: agent.description for name, agent in _registry.items()}


def setup_default_agents() -> None:
    """注册已实现的 Agent（新 Agent 实现后在此登记）"""
    if _registry:
        return
    from app.agent.answer_agent import AnswerAgent
    from app.agent.inquiry_agent import InquiryAgent
    from app.agent.rag_agent import RagAgent
    from app.agent.risk_agent import RiskAgent
    from app.agent.specialty_agent import SpecialtyAgent
    from app.agent.supervisor import SupervisorAgent
    from app.agent.symptom_agent import SymptomAgent

    register(SupervisorAgent())
    register(InquiryAgent())
    register(SymptomAgent())
    register(RagAgent())
    register(RiskAgent())
    register(SpecialtyAgent())
    register(AnswerAgent())
