"""回答 Agent：综合各 Agent 结果并生成最终回答（第五阶段）"""
import json
from typing import Any, Iterator

from app.agent.base import BaseAgent
from app.config.prompt import ANSWER_AGENT_PROMPT


class AnswerAgent(BaseAgent):
    """回答 Agent

    负责：整合 问诊结果 + 症状分析 + RAG 结果 + 风险评估 + 专科分析，
    生成结构化的最终回答，并在回答前做安全自审。
    """

    name = "answer"
    description = "回答 Agent：综合各 Agent 结果生成最终回答"
    system_prompt = ANSWER_AGENT_PROMPT

    @staticmethod
    def format_context(
        user_input: str,
        history: list[dict],
        plan: dict[str, Any],
        results: dict[str, Any],
    ) -> str:
        """把用户问题、历史和各 Agent 结果组装成回答 Agent 的输入"""
        return json.dumps(
            {
                "用户问题": user_input,
                "对话历史": history,
                "流程计划": plan,
                "问诊结果": results.get("inquiry", {}),
                "症状分析": results.get("symptom", ""),
                "知识库检索": results.get("rag", ""),
                "风险评估": results.get("risk", {}),
                "专科分析": results.get("specialty", ""),
            },
            ensure_ascii=False,
            indent=1,
        )

    def run(self, context: str, prompt_override: str | None = None) -> str:
        """非流式生成最终回答"""
        return super().run(context, prompt_override)

    def run_stream(self, context: str, prompt_override: str | None = None) -> Iterator[str]:
        """流式生成最终回答（向用户实时展示）"""
        yield from super().run_stream(context, prompt_override)
