"""检索结果重排序（第三阶段）：用 SiliconFlow 重排模型提高相关度"""
import httpx

from app.config import settings


def rerank(query: str, documents: list[str], top_n: int | None = None) -> list[dict]:
    """对候选文档重排序，返回按相关度降序的 [{index, score, text}]

    未配置 API Key 或文档为空时，直接按原顺序返回。
    """
    if not documents:
        return []
    if not settings.RERANK_API_KEY:
        return [{"index": i, "score": 0.0, "text": d} for i, d in enumerate(documents)]

    url = settings.RERANK_BASE_URL.rstrip("/") + "/rerank"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {settings.RERANK_API_KEY}"},
        json={"model": settings.RERANK_MODEL, "query": query, "documents": documents},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])

    ordered = sorted(results, key=lambda r: r.get("relevance_score", 0.0), reverse=True)
    if top_n is not None:
        ordered = ordered[:top_n]
    return [
        {"index": r["index"], "score": r["relevance_score"], "text": documents[r["index"]]}
        for r in ordered
    ]
