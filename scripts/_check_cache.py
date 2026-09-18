"""查 fastembed 模型缓存位置 + 下载机制（纯 Python，避免 shell 转义）"""
import os
import fastembed

pkg = os.path.dirname(fastembed.__file__)

# 1. 读取 onnx 模型基类源码，找 cache_dir 默认值 / 下载函数
import glob
for f in glob.glob(os.path.join(pkg, "**", "*.py"), recursive=True):
    with open(f, encoding="utf-8") as fh:
        src = fh.read()
    if "snapshot_download" in src or "hf_hub_download" in src or "local_cache" in src or "cache_dir" in src:
        print("=" * 70)
        print("文件:", f.replace(pkg, ""))
        for line in src.splitlines():
            if any(k in line for k in ["snapshot_download", "hf_hub_download", "cache_dir", "local_cache", "download"]):
                print("  ", line.strip()[:140])

# 2. 全盘找已下载的 jina 模型文件（大 onnx）
print("\n=== 查找已下载的 onnx 模型文件（>50MB）===")
for root, dirs, files in os.walk(os.path.expanduser("~")):
    if "/.venv" in root or "/site-packages" in root:
        continue
    for fn in files:
        if fn.endswith(".onnx") or "model" in fn and fn.endswith((".bin", ".gguf")):
            p = os.path.join(root, fn)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if sz > 50 * 1024 * 1024:
                print(f"  {sz/1024/1024:.0f}MB  {p}")
