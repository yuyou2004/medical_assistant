"""小规模端到端测试：5 页 -> 切分 -> 建临时向量库 -> 检索（首次会下载模型）"""
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_chroma import Chroma
from app.rag import loader, splitter
from app.rag.embedding import get_embeddings

tmp_dir = "/tmp/test_chroma"
shutil.rmtree(tmp_dir, ignore_errors=True)

print("[1] 加载前 5 页 ...")
docs = loader.load_pdf("app/rag/内科学(第10版).pdf")[:5]
chunks = splitter.split_documents(docs)
print("    切出 chunk 数:", len(chunks))

print("[2] 加载 embedding 模型（首次会下载到 ~/.cache/fastembed）...")
emb = get_embeddings()

print("[3] 写入临时 Chroma ...")
store = Chroma.from_documents(
    documents=chunks,
    embedding=emb,
    collection_name="test",
    persist_directory=tmp_dir,
)
print("    写入完成")

print("[4] 检索测试 ...")
for q in ["高血压", "冠心病", "呼吸"]:
    res = store.similarity_search(q, k=1)
    if res:
        print(f"    问题「{q}」-> 命中: {res[0].page_content[:50]}")
print("端到端 OK")
