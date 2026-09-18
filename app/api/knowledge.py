"""知识库接口（第三阶段）：POST /api/knowledge/search 检索 + GET /api/knowledge/stats 状态"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.rag_agent import RagAgent
from app.dao import knowledge_dao

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


class KnowledgeSearchRequest(BaseModel):
    """知识检索请求体"""

    query: str = Field(..., min_length=1, max_length=500, description="检索问题")
    top_k: int = Field(default=6, ge=1, le=20, description="向量召回数量")
    top_n: int = Field(default=3, ge=1, le=10, description="重排后保留数量")


@router.post("/search")
def search_knowledge(req: KnowledgeSearchRequest):
    """向量检索 + 重排，返回相关知识片段（含来源和页码）"""
    agent = RagAgent()
    items = agent.search(req.query, top_k=req.top_k, top_n=req.top_n)
    return {"query": req.query, "count": len(items), "items": items}


@router.get("/stats")
def knowledge_stats():
    """知识库状态：向量库 chunk 数 + 知识源 PDF 列表（不加载 embedding 模型，轻量）"""
    return {
        "chunk_count": knowledge_dao.get_chunk_count(),
        "pdfs": knowledge_dao.list_knowledge_sources(),
    }
