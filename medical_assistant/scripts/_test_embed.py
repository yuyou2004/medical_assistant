"""测试本地 embedding：首次运行会下载模型"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.embedding import get_embeddings

print("加载模型（首次会下载，请稍候）...")
e = get_embeddings()

v = e.embed_query("高血压的诊断标准是什么？")
print("query 向量维度:", len(v))

docs = e.embed_documents(["高血压是一种常见的心血管疾病。", "急性阑尾炎表现为右下腹疼痛。"])
print("文档向量维度:", len(docs[0]), "数量:", len(docs))

# 简单验证：语义相近的句子向量更接近
import numpy as np
q = np.asarray(e.embed_query("高血压怎么治疗"))
a = np.asarray(e.embed_query("高血压的药物治疗方案"))
b = np.asarray(e.embed_query("今天天气不错"))
print("相关句余弦相似度:", float(q @ a))
print("无关句余弦相似度:", float(q @ b))
