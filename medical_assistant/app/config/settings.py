"""全局配置：从项目根目录的 .env 文件读取环境变量"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录（app/config/settings.py 向上两级）
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 加载 .env 文件（不存在时静默跳过）
load_dotenv(BASE_DIR / ".env")

# ---------- 大模型配置（默认 DeepSeek，OpenAI 兼容接口，可换成其他兼容服务） ----------
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# ---------- 本地 Embedding 配置（fastembed / ONNX Runtime 本地推理，不依赖 torch） ----------
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "jinaai/jina-embeddings-v2-base-zh")
EMBEDDING_CACHE_DIR = os.getenv("EMBEDDING_CACHE_DIR", str(Path.home() / ".cache" / "fastembed"))
# ONNX Runtime 推理线程数：过大时内存占用激增（16 核默认全开可能 OOM），4 线程约占用 4GB 内
EMBEDDING_THREADS = int(os.getenv("EMBEDDING_THREADS", "4"))
# 向量化批量大小：越大越快但越吃内存；128 对应 400 字符 chunk 时约 4GB
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "128"))

# ---------- Rerank 配置（可选：SiliconFlow 云端重排；不配 key 则跳过重排） ----------
RERANK_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
RERANK_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

# ---------- RAG 知识库配置 ----------
RAG_PDF_DIR = os.getenv("RAG_PDF_DIR", str(BASE_DIR / "app" / "rag"))  # 待建库 PDF 所在目录
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", str(BASE_DIR / "data" / "vector_db"))  # 向量库持久化目录
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))

# ---------- 服务配置 ----------
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
