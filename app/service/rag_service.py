"""RAG 检索业务服务（第三阶段）：向量检索 + 重排，为上层提供知识上下文"""
from app.config import settings
from app.rag import reranker, retriever


def _to_items(docs: list) -> list[dict]:
    """把 LangChain Document 转成结构化字典，便于上层使用"""
    return [
        {
            "content": d.page_content,
            "source": d.metadata.get("source", ""),
            "page": d.metadata.get("page"),
        }
        for d in docs
    ]


def search(query: str, top_k: int | None = None) -> list[dict]:
    """纯向量检索：返回 top_k 个相关 chunk"""
    docs = retriever.retrieve(query, top_k)
    return _to_items(docs)


def search_with_rerank(query: str, top_k: int | None = None, top_n: int = 3) -> list[dict]:
    """向量召回 top_k 后，再用重排模型精排，返回 top_n 个最相关的 chunk"""
    docs = retriever.retrieve(query, top_k)
    texts = [d.page_content for d in docs]

    try:
        ranked = reranker.rerank(query, texts, top_n)
    except Exception:  # 重排失败时降级为按向量检索顺序返回
        ranked = [{"index": i, "score": 0.0, "text": t} for i, t in enumerate(texts[:top_n])]

    return [
        {
            "content": r["text"],
            "score": r["score"],
            "source": docs[r["index"]].metadata.get("source", ""),
            "page": docs[r["index"]].metadata.get("page"),
        }
        for r in ranked
    ]


def build_knowledge_base() -> int:
    """建库入口：加载 PDF -> 切分 -> 向量化 -> 写入 Chroma，返回 chunk 数量"""
    from app.rag import loader, splitter

    docs = loader.load_pdf_dir(settings.RAG_PDF_DIR)
    chunks = splitter.split_documents(docs)
    retriever.build_vector_store(chunks)
    return len(chunks)
