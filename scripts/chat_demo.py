"""终端聊天 Demo：输入一句话，大模型流式输出（不需要启动 Web 服务）

用法：
    uv run python scripts/chat_demo.py
    输入 exit / quit 退出
"""
import sys
from pathlib import Path

# 把项目根目录加入模块搜索路径，方便直接运行脚本
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.service.chat_service import chat_stream


def main():
    print(f"=== AI 医疗咨询助手（模型：{settings.LLM_MODEL}）===")
    if not settings.LLM_API_KEY:
        print("提示：未配置 DEEPSEEK_API_KEY，请先在 .env 文件中填写密钥")
        return

    history: list[dict] = []  # 保存多轮对话上下文
    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        # 流式输出：模型生成一段，终端打印一段
        print("AI：", end="", flush=True)
        full = ""
        try:
            for text in chat_stream(user_input, history):
                print(text, end="", flush=True)
                full += text
            print()
        except Exception as e:
            print(f"\n[调用失败] {e}，请检查 .env 中的 DEEPSEEK_API_KEY")
            continue

        # 更新历史，支持多轮对话
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": full})

    print("再见！")


if __name__ == "__main__":
    main()
