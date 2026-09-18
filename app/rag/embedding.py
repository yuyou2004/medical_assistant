"""文档向量化：本地 Jina Embeddings v2 中文模型推理（第三阶段）

用 fastembed（ONNX Runtime）本地推理，不依赖 torch。
模型：jinaai/jina-embeddings-v2-base-zh（768 维，中文检索效果强，支持 8k 上下文）。

注意：ONNX Runtime 并行线程与批大小直接决定内存峰值，
请通过 EMBEDDING_THREADS / EMBEDDING_BATCH_SIZE 配置，避免默认全核导致 OOM。
"""
import threading

import numpy as np
from fastembed import TextEmbedding
from langchain_core.embeddings import Embeddings

from app.config import settings

_embeddings: "LocalEmbeddings | None" = None
_lock = threading.Lock()  # 串行化推理调用，避免多请求并发时 ONNX session 竞争


class LocalEmbeddings(Embeddings):
    """本地 Embedding 模型封装（fastembed / ONNX Runtime），兼容 LangChain 接口"""

    def __init__(self) -> None:
        self.model = TextEmbedding(
            model_name=settings.EMBEDDING_MODEL_NAME,
            cache_dir=settings.EMBEDDING_CACHE_DIR,
            threads=settings.EMBEDDING_THREADS,
        )
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化：分批推理以控制内存峰值"""
        vectors: list[list[float]] = []
        with _lock:
            for vec in self.model.embed(texts, batch_size=self.batch_size):
                vectors.append(self._norm(vec))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        with _lock:
            vector = list(self.model.embed([text], batch_size=1))[0]
        return self._norm(vector)

    @staticmethod
    def _norm(v) -> list[float]:
        v = np.asarray(v, dtype="float32")
        return (v / np.linalg.norm(v)).tolist()


def get_embeddings() -> LocalEmbeddings:
    """返回全局共享的本地 Embedding 模型实例（首次调用会下载模型）"""
    global _embeddings
    if _embeddings is None:
        with _lock:
            if _embeddings is None:
                _embeddings = LocalEmbeddings()
    return _embeddings
