"""RAG Agent：医疗知识检索（第五阶段）"""
import logging

from app.agent.base import BaseAgent
from app.config import settings
from app.service import rag_service

logger = logging.getLogger(__name__)


class RagAgent(BaseAgent):
    """RAG Agent

    负责：构建检索请求、检索医疗知识、筛选相关知识、为其他 Agent 提供知识支持。
    检索直接用向量库（本地 embedding），不调用大模型；知识来源会随结果一起返回，
    供回答 Agent 引用。
    """

    name = "rag"
    description = "RAG Agent：医疗知识检索"
    system_prompt = "你负责从医疗知识库中检索与用户问题相关的知识。"

    def search(self, query: str, top_k: int | None = None, top_n: int | None = None) -> list[dict]:
        """向量召回 + 重排精筛，返回 [{content, score, source, page}]"""
        try:
            return rag_service.search_with_rerank(
                query,
                top_k=top_k or settings.RAG_TOP_K,
                top_n=top_n or settings.RERANK_TOP_N,
            )
        except Exception:
            # 知识库未建或检索失败时降级为空结果，不让整个咨询流程中断
            logger.exception("RAG 检索失败（知识库可能未建立）")
            return []

    @staticmethod
    def format_knowledge(items: list[dict]) -> str:
        """把检索结果格式化为带来源标注的知识文本（供回答 Agent 引用）"""
        if not items:
            return "（知识库未检索到相关内容，请基于模型自身知识谨慎回答，并提示知识来源不足）"
        parts = [
            f"[{i}] {it['content']}（来源：{it['source']} 第 {it.get('page', '?')} 页）"
            for i, it in enumerate(items, 1)
        ]
        return "医疗知识库检索结果：\n" + "\n\n".join(parts)

    def run(self, context: str) -> str:
        """检索并格式化为知识文本（带来源标注），供回答 Agent 使用

        Args:
            context: 检索请求（用用户最新输入直接检索，中文向量检索效果稳定）
        """
        logger.info("Agent [%s] 开始检索", self.name)
        return self.format_knowledge(self.search(context))
