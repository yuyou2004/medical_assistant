"""体检报告解读接口（M9 扩展）：POST /api/report/analyze

链路（多智能体思想，与图片问诊链路复用）：
    体检报告文本 → 直接进入解读
    体检报告图片 → 视觉大模型提取报告原文 → 大模型逐项解读
解读按指标逐项输出（名称/检测值/参考范围/评估/建议），并给出整体建议与风险分级。

说明：视觉提取依赖 SILICONFLOW_API_KEY（与图片问诊共用）；文本解读依赖
DEEPSEEK_API_KEY。解读结果仅供健康参考，不构成医疗诊断。
"""
import base64
import logging

import httpx
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings
from app.service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report", tags=["体检报告"])

# 视觉模型：从报告图片中提取原文（OCR 角色，不解读）
REPORT_OCR_PROMPT = """这是一张体检/化验报告图片。请把图片中能看到的全部文字内容原样提取出来，
包括：检查项目名称、检测结果、数值、单位、参考范围、报告日期等，按行输出。
不要解读、不要评论、不要补充图片中没有的内容。"""

# 解读模型：按指标逐项解读
REPORT_INTERPRET_PROMPT = """你是一名全科医生助手，负责解读体检报告。请基于用户提供的报告内容，
逐项解读每个检测指标，按以下 JSON 格式输出（不要输出任何其他内容）：
{
 "summary": "报告整体情况概述（2-3 句）",
 "items": [
   {"name": "指标名称", "value": "检测值", "reference": "参考范围（报告未给可填'未提供'）",
    "assessment": "正常/偏高/偏低 + 该项的简明解读（结合参考范围判断）",
    "advice": "针对该项的建议（无异常可写'无需特殊处理'）"}
 ],
 "overall_advice": "总体建议（饮食/运动/复查/就诊方向）",
 "risk_level": "低风险/中风险/高风险/无法判断（多项明显异常或危急值判高风险）"
}
要求：只解读报告中出现的指标；无法判断时如实说明；结尾不要添加免责声明以外的内容。"""


def _require_llm() -> None:
    if not settings.LLM_CONFIGURED:
        raise HTTPException(status_code=503, detail="报告解读未启用：请在 .env 中配置 DEEPSEEK_API_KEY 后重启服务")


def _extract_report_text(file: UploadFile) -> str:
    """用视觉模型从报告图片提取原文（与图片问诊共用 SiliconFlow 视觉链路）"""
    if not settings.VISION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="报告图片识别未启用：请在 .env 中配置 SILICONFLOW_API_KEY（硅基流动官网免费申请，模型 " + settings.VISION_MODEL + "）后重启服务",
        )
    content = file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(content) > settings.MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"图片不能超过 {settings.MAX_IMAGE_SIZE_MB}MB")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件（jpg/png/webp 等）")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    data_url = f"data:{mime};base64,{base64.b64encode(content).decode()}"

    try:
        with httpx.Client(timeout=90) as client:
            resp = client.post(
                settings.VISION_BASE_URL.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {settings.VISION_API_KEY}"},
                json={
                    "model": settings.VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": REPORT_OCR_PROMPT},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        }
                    ],
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error("视觉模型调用失败：%s", e)
        raise HTTPException(status_code=502, detail="报告图片识别失败，请稍后重试")
    except httpx.HTTPError as e:
        logger.error("视觉模型网络异常：%s", e)
        raise HTTPException(status_code=502, detail="报告图片识别网络异常，请稍后重试")
    return text


def _interpret(report_text: str) -> dict:
    """逐项解读报告文本，返回结构化结果"""
    messages = [
        {"role": "system", "content": REPORT_INTERPRET_PROMPT},
        {"role": "user", "content": f"体检报告内容如下：\n\n{report_text}"},
    ]
    try:
        result = llm_service.chat_json(messages, temperature=0.2)
    except RuntimeError as e:
        logger.exception("报告解读失败")
        raise HTTPException(status_code=502, detail="报告解读失败，请稍后重试或改用文字输入")
    if not isinstance(result.get("items"), list):
        raise HTTPException(status_code=502, detail="报告解读返回格式异常，请重试")
    return result


@router.post("/analyze")
def analyze_report(
    text: str | None = Form(default=None, description="报告文本内容（与文件二选一）"),
    file: UploadFile | None = None,
):
    """解读体检报告：文本直接解读；图片先视觉提取再解读"""
    if text and text.strip():
        report_text = text.strip()
        if len(report_text) > 20000:
            raise HTTPException(status_code=400, detail="报告文本过长（最多 20000 字）")
        source = "text"
    elif file is not None:
        report_text = _extract_report_text(file)
        source = "image"
    else:
        raise HTTPException(status_code=400, detail="请提供报告文本或图片文件")

    _require_llm()
    result = _interpret(report_text)
    return JSONResponse({
        "source": source,
        "filename": file.filename if file else None,
        "result": result,
        "disclaimer": "报告解读仅供健康参考，不构成医疗诊断；如有异常指标，请携带报告到正规医院咨询医生",
    })
