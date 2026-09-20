"""图片问诊接口（M8 扩展）：POST /api/vision/analyze 上传图片，视觉大模型识别皮肤病变等

说明：视觉识别依赖 SiliconFlow 多模态视觉模型（.env 配置 SILICONFLOW_API_KEY，
官网可免费申请）；未配置时返回 503 并给出配置指引，前端做优雅降级提示。
"""
import base64
import json
import logging

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vision", tags=["图片问诊"])

VISION_PROMPT = """你是一名皮肤科医生助手。请仔细观察这张图片，按以下 JSON 格式输出（不要输出任何其他内容）：
{"description": "对图片中皮损/异常部位的客观描述（位置、颜色、形态、范围）",
 "possible_conditions": "可能的皮肤问题（按可能性排序，2-3 个，注意：图片诊断仅供参考，不能替代面诊）",
 "advice": "给用户的护理建议与就医建议（如：避免抓挠、注意防晒、建议尽快就诊等）",
 "risk_level": "低风险/中风险/高风险（出现破溃渗液、快速扩散、疼痛剧烈等判为高风险）"}"""


@router.post("/analyze")
async def analyze_image(file: UploadFile):
    """上传图片 → 视觉模型识别（皮肤科为主），返回结构化分析结果"""
    if not settings.VISION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="图片问诊未启用：请在 .env 中配置 SILICONFLOW_API_KEY（硅基流动官网免费申请，模型 " + settings.VISION_MODEL + "）后重启服务",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片内容为空")
    if len(content) > settings.MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"图片不能超过 {settings.MAX_IMAGE_SIZE_MB}MB")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件（jpg/png/webp 等）")

    # 统一转 base64 送视觉模型
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    data_url = f"data:{mime};base64,{base64.b64encode(content).decode()}"

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                settings.VISION_BASE_URL.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {settings.VISION_API_KEY}"},
                json={
                    "model": settings.VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": VISION_PROMPT},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        }
                    ],
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error("视觉模型调用失败：%s", e)
        raise HTTPException(status_code=502, detail="视觉模型调用失败，请稍后重试")
    except httpx.HTTPError as e:
        logger.error("视觉模型网络异常：%s", e)
        raise HTTPException(status_code=502, detail="视觉模型网络异常，请稍后重试")

    # 解析模型输出的 JSON（模型可能包裹在 ```json 代码块里，做容错）
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            result = json.loads(text[start:end])
        except Exception:
            result = {
                "description": text,
                "possible_conditions": "",
                "advice": "",
                "risk_level": "无法判断",
            }
    return JSONResponse({
        "filename": file.filename,
        "result": result,
        "disclaimer": "图片识别结果仅供健康参考，不构成医疗诊断，请务必到正规医院皮肤科面诊确认",
    })
