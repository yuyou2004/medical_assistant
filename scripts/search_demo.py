"""检索演示：建库后测试知识检索效果

用法（在项目根目录下）：
    .venv/bin/python scripts/search_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.service.rag_service import search_with_rerank

QUERIES = [
    "高血压的诊断标准是什么？",
    "急性阑尾炎的典型表现有哪些？",
    "糖尿病的慢性并发症有哪些？",
    "骨折的急救处理原则？",
]


def main() -> None:
    for q in QUERIES:
        print(f"\n{'=' * 60}\n问题：{q}\n{'=' * 60}")
        try:
            items = search_with_rerank(q, top_n=3)
            for i, it in enumerate(items, 1):
                src = Path(it["source"]).name if it["source"] else "?"
                print(f"\n[{i}] score={it['score']:.3f}  来源={src} 第{it['page']}页")
                print(f"    {it['content'][:120]}")
        except Exception as e:
            print(f"检索失败：{e}")


if __name__ == "__main__":
    main()
