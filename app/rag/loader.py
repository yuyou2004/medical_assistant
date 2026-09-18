"""知识加载：读取 PDF 医疗文档，抽取出纯文本（第三阶段）

直接用 PyMuPDF（fitz）抽取文本，不依赖已停用的 langchain-community。
"""
from pathlib import Path

import pymupdf
from langchain_core.documents import Document


def load_pdf(pdf_path: str | Path) -> list[Document]:
    """加载单个 PDF，返回 LangChain Document 列表（每页一个 Document）

    Document 的 metadata 里带上 source（文件路径）和 page（页码，从 0 开始）。
    """
    pdf_path = Path(pdf_path)
    docs: list[Document] = []
    with pymupdf.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if text:
                docs.append(
                    Document(
                        page_content=text,
                        metadata={"source": str(pdf_path), "page": i},
                    )
                )
    return docs


def load_pdf_dir(pdf_dir: str | Path) -> list[Document]:
    """加载目录下所有 PDF，返回全部 Document 列表"""
    pdf_dir = Path(pdf_dir)
    docs: list[Document] = []
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        docs.extend(load_pdf(pdf))
    return docs
