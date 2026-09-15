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

# ---------- 服务配置 ----------
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
