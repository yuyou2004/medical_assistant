"""文档切分：把长文档切成带重叠的小块，便于向量化和检索（第三阶段）"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


def get_splitter() -> RecursiveCharacterTextSplitter:
    """构造中文友好的文本切分器

    separators 里放入中文句读符号，切分时优先在段落、句子边界断开，
    避免把一句话切到两个 chunk 里。chunk_size / overlap 走配置。
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        keep_separator=True,
    )


def split_documents(docs: list) -> list:
    """把 Document 列表切分成更小的 chunk"""
    return get_splitter().split_documents(docs)
