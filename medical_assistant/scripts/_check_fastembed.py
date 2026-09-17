"""检查 fastembed 是否支持自定义 ONNX 模型加载"""
import os
import fastembed

pkg_dir = os.path.dirname(fastembed.__file__)
print("fastembed 目录:", pkg_dir)

# 1. 查找是否有 large-zh 相关引用
import subprocess
r = subprocess.run(
    ["grep", "-rl", "large-zh", pkg_dir], capture_output=True, text=True
)
print("\n含 large-zh 的文件:", r.stdout.strip() or "无")

# 2. 看 TextEmbedding 如何解析 model_name
from fastembed.text.text_embedding import TextEmbedding
src = open(os.path.join(pkg_dir, "text", "text_embedding.py")).read()
# 打印含关键词的片段
for kw in ["model_name", "supported", "not supported", "resolve", "huggingface", "onnx"]:
    lines = [l.strip() for l in src.splitlines() if kw in l]
    if lines:
        print(f"\n=== 关键词 '{kw}' ===")
        for l in lines[:6]:
            print("  ", l[:140])
