"""终端智能体 Demo：与 Supervisor 对话，展示完整多智能体会诊流程

用法：
    uv run python scripts/agent_demo.py
    输入 exit / quit 退出

流程展示：路由计划 → 问诊（多轮追问）→ 症状/RAG/风险并行 → 专科 → 流式回答
"""
import sys
from pathlib import Path

# 把项目根目录加入模块搜索路径，方便直接运行脚本
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import get_agent, setup_default_agents
from app.config import settings


def main():
    setup_default_agents()
    print(f"=== AI 医疗咨询助手 · 多智能体会诊（模型：{settings.LLM_MODEL}）===")
    print("流程：Supervisor 路由 → 问诊 Agent 多轮追问 → 症状/RAG/风险并行分析 → 专科 → 综合回答\n")
    if not settings.LLM_CONFIGURED:
        print("提示：未配置 DEEPSEEK_API_KEY，请先在 .env 文件中填写密钥")
        return

    supervisor = get_agent("supervisor")
    history: list[dict] = []

    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break
        if len(user_input) > settings.MAX_MESSAGE_LENGTH:
            print(f"[提示] 单条消息不能超过 {settings.MAX_MESSAGE_LENGTH} 字")
            continue

        answer = ""
        for event in supervisor.orchestrate(user_input, history):
            if event["type"] == "plan":
                data = event["data"]
                print(
                    f"[Supervisor 计划] 下一步 → {data.get('next_agent')}（{data.get('reason')}）"
                )
            elif event["type"] == "agent":
                data = event["data"]
                result = str(data.get("result", ""))
                if len(result) > 300:
                    result = result[:300] + "……"
                print(f"[Agent 执行] {data.get('name')}：{result}")
            elif event["type"] == "question":
                answer = event["data"]
                print(f"\n助手：{answer}")
            elif event["type"] == "content":
                text = event["data"]
                answer += text
                print(text, end="", flush=True)
            elif event["type"] == "done":
                data = event["data"]
                meta = []
                if data.get("risk_level"):
                    meta.append(f"风险等级：{data['risk_level']}")
                if data.get("sources"):
                    meta.append(f"知识来源：{len(data['sources'])} 条")
                if meta:
                    print(f"\n[完成] {'；'.join(meta)}")

        # 更新历史，支持多轮问诊（只保留最近 N 条）
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": answer})
        history = history[-settings.MAX_HISTORY_MESSAGES:]

    print("再见！")


if __name__ == "__main__":
    main()
