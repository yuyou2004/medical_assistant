# 多智能体协同 RAG 医疗咨询助手

基于大语言模型 + RAG + Multi-Agent 的 AI 智能问诊辅助系统。完整设计见 [RAG医疗v3.md.md](RAG医疗v3.md.md)。

## 目录结构

```text
medical_assistant/
├── app/                    # 应用代码
│   ├── api/                # API 接口层（chat.py 已实现）
│   ├── service/            # 业务逻辑层（chat_service.py 已实现）
│   ├── dao/                # 数据访问层
│   ├── model/              # 数据模型
│   ├── agent/              # 多智能体模块
│   ├── rag/                # RAG 知识检索模块
│   ├── workflow/           # Agent 工作流
│   ├── data/               # 知识数据（raw / processed / medical）
│   ├── config/             # 配置（settings.py / prompt.py）
│   └── main.py             # 项目入口
├── tests/                  # 测试
├── scripts/                # 脚本（chat_demo.py：终端聊天 Demo）
├── docker/                 # Docker 配置
├── .env                    # 环境变量（密钥，不入库）
├── requirements.txt
└── pyproject.toml
```

## 快速开始

1. 配置密钥：复制 `.env.example` 为 `.env`（项目已有 `.env` 模板），填写 `DEEPSEEK_API_KEY`

2. 安装依赖：

   ```bash
   uv sync
   ```

3. 启动后端服务：

   ```bash
   uv run uvicorn app.main:app --reload
   # 或
   uv run python app/main.py
   ```

4. 测试聊天接口（SSE 流式输出）：

   ```bash
   curl -N -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "最近总是睡不好怎么办？"}'
   ```

   接口文档：http://localhost:8000/docs

5. 终端聊天 Demo（不启动 Web 服务，直接输入、流式输出）：

   ```bash
   uv run python scripts/chat_demo.py
   ```

## 开发阶段

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| M1 | 需求分析 | ✅ 已完成（见 RAG医疗v3.md.md） |
| M2 | 基础后端（FastAPI + 基础聊天 API） | 🚧 进行中 |
| M3 | RAG 知识库 | 待开发 |
| M4 | 单 Agent 医疗咨询 | 待开发 |
| M5 | Multi-Agent | 待开发 |
| M6 | Agent 协同（Supervisor + LangGraph） | 待开发 |
| M7 | 系统整合 | 待开发 |
| M8 | 测试与优化 | 待开发 |
| M9 | Docker 部署 | 待开发 |
