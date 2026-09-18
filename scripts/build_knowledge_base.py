"""建库脚本：把 PDF 解析 -> 切分 -> 向量化 -> 分批写入 Chroma

用法（在项目根目录下）：
    .venv/bin/python scripts/build_knowledge_base.py

前置条件：embedding 模型已缓存（首次会自动下载）；.env 可配置 RAG 参数。
内存说明：向量化按 EMBEDDING_BATCH_SIZE 分批执行并即时入库，
不会一次性持有全部向量；若内存吃紧可调小批大小/线程数。
"""
import sys
import time
from pathlib import Path

# 保证能 import 到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.rag import loader, splitter
from app.rag.retriever import build_vector_store


def main() -> None:
    pdf_dir = Path(settings.RAG_PDF_DIR)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"未找到 PDF，请检查目录：{pdf_dir}")
        return
    print("待建库 PDF：")
    for p in pdfs:
        print(f"  - {p.name} ({p.stat().st_size / 1024 / 1024:.1f} MB)")

    t_start = time.time()

    print("\n[1/3] 解析 PDF ...")
    docs = loader.load_pdf_dir(pdf_dir)
    print(f"      共解析 {len(docs)} 页（{time.time() - t_start:.0f}s）")

    print("[2/3] 切分文本 ...")
    chunks = splitter.split_documents(docs)
    print(f"      共切分 {len(chunks)} 个 chunk")
    print(f"      chunk_size={settings.CHUNK_SIZE}, overlap={settings.CHUNK_OVERLAP}")
    del docs  # 释放整页文本内存

    print("[3/3] 向量化并分批写入 Chroma ...")
    print(f"      批大小={settings.EMBEDDING_BATCH_SIZE}, 线程={settings.EMBEDDING_THREADS}")
    n = build_vector_store(chunks)
    del chunks

    elapsed = time.time() - t_start
    print(f"\n完成！写入 {n} 个 chunk，总耗时 {elapsed / 60:.1f} 分钟")
    print(f"向量库存于：{settings.VECTOR_DB_DIR}")


if __name__ == "__main__":
    main()
