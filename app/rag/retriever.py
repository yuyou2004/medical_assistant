"""向量检索：Chroma 向量库 + 相似度检索（第三阶段）"""
import shutil

import chromadb
from langchain_chroma import Chroma

from app.config import settings
from app.rag.embedding import get_embeddings

COLLECTION_NAME = "medical_knowledge"


def get_vector_store() -> Chroma:
    """打开（或新建）持久化的 Chroma 向量库"""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=settings.VECTOR_DB_DIR,
    )


def build_vector_store(docs: list, batch_size: int | None = None) -> int:
    """把切分好的 chunk 向量化并分批写入向量库（重建：先清空旧库）

    内存控制：逐批向量化并立即写入，避免一次性持有全部向量。
    返回写入的 chunk 总数。
    """
    batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

    # 删除旧库目录，避免重复建库时数据叠加
    shutil.rmtree(settings.VECTOR_DB_DIR, ignore_errors=True)

    client = chromadb.PersistentClient(path=settings.VECTOR_DB_DIR)
    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    embeddings_model = get_embeddings()
    total = 0
    for start in range(0, len(docs), batch_size):
        batch = docs[start : start + batch_size]
        texts = [d.page_content for d in batch]
        ids = [f"chunk_{start + j}" for j in range(len(batch))]
        metadatas = [
            {
                "source": d.metadata.get("source", ""),
                "page": d.metadata.get("page", 0),
            }
            for d in batch
        ]
        vectors = list(embeddings_model.model.embed(texts, batch_size=batch_size))
        collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )
        total += len(batch)
        print(f"    +{len(batch)} chunks（累计 {total}/{len(docs)}）", flush=True)
    return total


def retrieve(query: str, top_k: int | None = None) -> list:
    """按语义相似度检索 top_k 个相关 chunk"""
    store = get_vector_store()
    k = top_k or settings.RAG_TOP_K
    return store.similarity_search(query, k=k)
