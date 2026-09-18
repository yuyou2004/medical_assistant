"""Supervisor Agent：总协调，负责任务判断、Agent 路由与流程控制（第六阶段）

业务流程（设计文档第九节）：
    用户提问
      → 问诊 Agent 收集信息
      → 信息是否足够？
        否 → 继续问诊（多轮追问，直接把问题返回给用户）
        是 → 症状分析 + RAG 检索 + 风险评估（并行）
            → 专科分析
            → 综合回答（含安全自审）
            → 用户
知识类问题（非症状咨询）走捷径：RAG 检索 → 综合回答。
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterator

from app.agent import get_agent, list_agents
from app.agent.answer_agent import AnswerAgent
from app.agent.base import BaseAgent
from app.agent.rag_agent import RagAgent
from app.config import settings
from app.config.prompt import AGENT_PLAN_PROMPT, KNOWLEDGE_ANSWER_PROMPT, SUPERVISOR_PROMPT
from app.service import llm_service

logger = logging.getLogger(__name__)


def _build_context(user_input: str, history: list[dict]) -> str:
    """把历史对话 + 最新输入拼成给 Agent 的上下文"""
    return json.dumps(
        {"对话历史": history, "用户最新输入": user_input},
        ensure_ascii=False,
    )


def _safe_run(agent: BaseAgent, context: str):
    """执行 Agent 并兜底异常，保证单个 Agent 失败不中断整个流程"""
    try:
        return agent.run(context)
    except Exception:
        logger.exception("Agent [%s] 执行失败", agent.name)
        return f"[{agent.name} 执行失败，本次结果缺失]"


class SupervisorAgent(BaseAgent):
    """总协调 Agent（Super）

    负责：判断任务类型 → 调度各 Agent → 控制流程 → 传递上下文 → 判断是否结束。
    所有子 Agent 均已实现，按设计文档第九节流程协同工作。
    """

    name = "supervisor"
    description = "总协调 Agent：任务判断、Agent 路由、流程控制"
    system_prompt = SUPERVISOR_PROMPT

    def plan(self, user_input: str, context: str = "") -> dict[str, Any]:
        """分析当前情况，输出路由计划（JSON，格式见 AGENT_PLAN_PROMPT）

        路由规则：知识类问题 → rag；症状咨询 → inquiry；闲聊 → finish。
        """
        options = list_agents()
        options.pop(self.name, None)  # Supervisor 自己不在被调度范围内
        option_text = "；".join(f"{name}（{desc}）" for name, desc in options.items())

        messages = [
            {"role": "system", "content": SUPERVISOR_PROMPT},
            {
                "role": "user",
                "content": AGENT_PLAN_PROMPT.format(
                    agent_options=option_text,
                    user_input=user_input,
                    context=context,
                ),
            },
        ]
        return llm_service.chat_json(messages)

    def orchestrate(self, user_input: str, history: list[dict] | None = None) -> Iterator[dict]:
        """总控流程，以生成器方式逐个产出事件（供 SSE 流式推送）

        事件类型：
        - plan：Supervisor 的路由计划（{"next_agent": ..., "reason": ...}）
        - agent：某个子 Agent 的执行结果（{"name", "description", "result"}）
        - question：问诊追问内容（信息不足时直接作为回复给用户）
        - content：最终回答的文本片段（逐段流式）
        - done：流程结束（含 stage / risk_level / sources 等元信息）
        - error：流程失败
        """
        history = (history or [])[-settings.MAX_HISTORY_MESSAGES:]
        context = json.dumps(history, ensure_ascii=False)

        # 1. 规划：判断任务类型（知识问题 / 症状咨询）
        try:
            plan = self.plan(user_input, context)
        except Exception:
            logger.exception("Supervisor 规划失败，默认进入问诊流程")
            plan = {"next_agent": "inquiry", "reason": "规划失败，默认进入问诊流程"}
        yield {"type": "plan", "data": plan}

        try:
            if str(plan.get("next_agent", "")) == "rag":
                # 知识类问题：RAG 检索 + 综合回答（捷径）
                yield from self._knowledge_flow(user_input, history, plan)
            else:
                # 症状咨询：完整问诊流程
                yield from self._consultation_flow(user_input, history, plan)
        except Exception:
            logger.exception("Supervisor 总控流程失败")
            yield {"type": "error", "data": "流程执行失败，服务暂时不可用"}

    def _consultation_flow(self, user_input: str, history: list[dict], plan: dict) -> Iterator[dict]:
        """症状咨询主流程：问诊 → （信息不足则追问）→ 并行分析 → 专科 → 综合回答"""
        results: dict[str, Any] = {}

        # 2. 问诊 Agent：收集信息、判断是否完整
        inquiry = get_agent("inquiry")
        inquiry_result = _safe_run(inquiry, _build_context(user_input, history))
        if isinstance(inquiry_result, str):  # 兜底文本转结构
            inquiry_result = {"info_complete": True, "next_question": None, "collected": {}, "summary": inquiry_result}
        results["inquiry"] = inquiry_result
        yield {
            "type": "agent",
            "data": {
                "name": inquiry.name,
                "description": inquiry.description,
                "result": json.dumps(inquiry_result, ensure_ascii=False),
            },
        }

        # 追问轮数达到上限时强制进入分析（避免无限追问）
        rounds = 1 + sum(1 for m in history if m.get("role") == "user")
        if not inquiry_result.get("info_complete") and rounds <= settings.MAX_INQUIRY_ROUNDS:
            question = inquiry_result.get("next_question") or "可以再详细描述一下你的症状吗？"
            yield {"type": "question", "data": question}
            yield {"type": "done", "data": {"stage": "inquiry", "info_complete": False}}
            return

        # 3. 并行执行：症状分析 + RAG 检索 + 风险评估
        rag_agent: RagAgent = get_agent("rag")
        risk_ctx = json.dumps(
            {"对话": history, "用户最新输入": user_input, "问诊收集": inquiry_result},
            ensure_ascii=False,
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_symptom = pool.submit(_safe_run, get_agent("symptom"), _build_context(user_input, history))
            f_rag = pool.submit(rag_agent.search, user_input)
            f_risk = pool.submit(_safe_run, get_agent("risk"), risk_ctx)
            symptom_result = f_symptom.result()
            rag_items = f_rag.result()
            risk_result = f_risk.result()

        results["symptom"] = symptom_result
        yield {
            "type": "agent",
            "data": {"name": "symptom", "description": get_agent("symptom").description, "result": symptom_result},
        }

        rag_text = RagAgent.format_knowledge(rag_items)
        results["rag"] = rag_text
        yield {
            "type": "agent",
            "data": {
                "name": "rag",
                "description": rag_agent.description,
                "result": rag_text[:500] + ("……" if len(rag_text) > 500 else ""),
            },
        }

        if isinstance(risk_result, str):  # 兜底文本转结构
            risk_result = {"risk_level": "无法判断", "danger_signals": [], "analysis": risk_result, "advice": ""}
        results["risk"] = risk_result
        yield {
            "type": "agent",
            "data": {
                "name": "risk",
                "description": get_agent("risk").description,
                "result": json.dumps(risk_result, ensure_ascii=False),
            },
        }

        # 4. 专科分析（依赖症状分析和风险评估结果）
        specialty = get_agent("specialty")
        specialty_ctx = json.dumps(
            {"症状分析": symptom_result, "风险评估": risk_result}, ensure_ascii=False
        )
        specialty_result = _safe_run(specialty, specialty_ctx)
        results["specialty"] = specialty_result
        yield {
            "type": "agent",
            "data": {"name": "specialty", "description": specialty.description, "result": specialty_result},
        }

        # 5. 综合回答（流式，回答 Agent 内置安全自审）
        answer_ctx = AnswerAgent.format_context(user_input, history, plan, results)
        for text in get_agent("answer").run_stream(answer_ctx):
            yield {"type": "content", "data": text}

        yield {
            "type": "done",
            "data": {
                "stage": "finished",
                "risk_level": risk_result.get("risk_level"),
                "sources": [
                    {"source": it["source"], "page": it.get("page")} for it in rag_items
                ],
            },
        }

    def _knowledge_flow(self, user_input: str, history: list[dict], plan: dict) -> Iterator[dict]:
        """知识类问题捷径：RAG 检索 → 综合回答"""
        rag_agent: RagAgent = get_agent("rag")
        rag_items = rag_agent.search(user_input)
        rag_text = RagAgent.format_knowledge(rag_items)
        yield {
            "type": "agent",
            "data": {"name": "rag", "description": rag_agent.description, "result": rag_text[:500] + ("……" if len(rag_text) > 500 else "")},
        }

        # 知识问答专用提示词（不用问诊模板，避免出现"未提供血压数值"等问诊措辞）
        answer_ctx = json.dumps(
            {"用户问题": user_input, "对话历史": history, "知识库检索结果": rag_text},
            ensure_ascii=False,
            indent=1,
        )
        for text in get_agent("answer").run_stream(answer_ctx, KNOWLEDGE_ANSWER_PROMPT):
            yield {"type": "content", "data": text}

        yield {
            "type": "done",
            "data": {
                "stage": "finished",
                "sources": [
                    {"source": it["source"], "page": it.get("page")} for it in rag_items
                ],
            },
        }
