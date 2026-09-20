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

# 密钥是否已配置（为空或仍是占位符时视为未配置）
LLM_CONFIGURED = bool(LLM_API_KEY) and LLM_API_KEY != "sk-your-api-key-here"

# ---------- 对话限制 ----------
MAX_MESSAGE_LENGTH = 2000  # 单条消息最大长度（字符）
MAX_HISTORY_MESSAGES = 20  # 最多携带的历史消息条数（约 10 轮对话）
MAX_INQUIRY_ROUNDS = 3  # 问诊最多追问轮数，超过后强制进入分析（避免无限追问）

# ---------- 本地 Embedding 配置（fastembed / ONNX Runtime 本地推理，不依赖 torch） ----------
# 国内访问 HuggingFace 受限，模型下载走 hf-mirror 镜像（已被环境变量指定时优先用之）
os.environ.setdefault("HF_ENDPOINT", os.getenv("HF_ENDPOINT", "https://hf-mirror.com"))
# 镜像不支持 HuggingFace 的 Xet 存储后端，禁用后走普通 HTTP 下载
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
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
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "3"))  # 重排后保留的知识片段数

# ---------- 视觉识别配置（图片问诊：复用 SiliconFlow 多模态视觉模型；不配 key 则图片问诊不可用） ----------
VISION_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
VISION_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
VISION_MODEL = os.getenv("VISION_MODEL", "Qwen/Qwen2.5-VL-32B-Instruct")
VISION_ENABLED = bool(VISION_API_KEY) and VISION_API_KEY != "sk-your-api-key-here"
MAX_IMAGE_SIZE_MB = 8  # 图片上传大小上限（MB）

# ---------- RAG 知识库配置 ----------
# ChromaDB 关闭匿名遥测：少一次外发探测，启动更快（必须在 chromadb 导入前设置）
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
RAG_PDF_DIR = os.getenv("RAG_PDF_DIR", str(BASE_DIR / "app" / "rag"))  # 待建库 PDF 所在目录
VECTOR_DB_DIR = os.getenv("VECTOR_DB_DIR", str(BASE_DIR / "data" / "vector_db"))  # 向量库持久化目录
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))

# ---------- 服务配置 ----------
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# ---------- MySQL 配置（M7 系统整合：未启用时历史记录/用户功能退回内存实现） ----------
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "medical_assistant")
DB_ENABLED = os.getenv("MYSQL_ENABLED", "") == "1"
