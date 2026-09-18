"""知识库数据访问（第三阶段：RAG 知识库）：知识源元数据与统计

说明：知识片段向量由 ChromaDB 持久化（data/vector_db），不落 MySQL；
这里只负责知识库状态信息的查询（chunk 数、PDF 清单），供 /api/knowledge/stats 使用。
"""
import logging
from pathlib import Path

import chromadb

from app.config import settings
from app.rag.retriever import COLLECTION_NAME

logger = logging.getLogger(__name__)


def get_chunk_count() -> int:
    """向量库 chunk 总数；库不可用时返回 0"""
    try:
        client = chromadb.PersistentClient(path=settings.VECTOR_DB_DIR)
        return client.get_collection(COLLECTION_NAME).count()
    except Exception:
        logger.warning("向量库不可用（尚未建库？），chunk 数按 0 计")
        return 0


def list_knowledge_sources() -> list[dict]:
    """知识源 PDF 清单（名称 + 大小，MB）"""
    return [
        {"name": p.name, "size_mb": round(p.stat().st_size / 1024 / 1024, 1)}
        for p in sorted(Path(settings.RAG_PDF_DIR).glob("*.pdf"))
    ]
