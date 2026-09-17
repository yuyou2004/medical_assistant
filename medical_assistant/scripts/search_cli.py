"""交互式检索测试：输入任意医疗问题，回车即返回知识库命中的原文片段

用法（在项目根目录下）：
    .venv/bin/python scripts/search_cli.py
    输入 exit / quit 退出
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.retriever import retrieve


def main() -> None:
    print("=== RAG 知识库检索测试（输入 exit 退出）===")
    print("提示：首次运行需加载 embedding 模型，约 30 秒\n")
    while True:
        try:
            q = input("问题：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit"):
            break

        hits = retrieve(q, top_k=3)
        if not hits:
            print("  （未检索到相关内容）")
            continue
        for i, d in enumerate(hits, 1):
            src = Path(d.metadata.get("source", "")).name
            page = d.metadata.get("page", "?")
            text = d.page_content.replace("\n", " ")[:110]
            print(f"\n[{i}] {src} 第{page}页")
            print(f"    {text}")
        print()


if __name__ == "__main__":
    main()
