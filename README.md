# 多智能体协同 RAG 医疗咨询助手

基于大语言模型 + RAG + Multi-Agent 的 AI 智能问诊辅助系统。完整设计见 [RAG医疗v3.md.md](RAG医疗v3.md.md)。

## 目录结构

```text
medical_assistant/
├── app/                    # 应用代码
│   ├── api/                # API 接口层（chat.py / agent.py 已实现）
│   ├── service/            # 业务逻辑层（chat_service.py / llm_service.py 已实现）
│   ├── dao/                # 数据访问层
│   ├── model/              # 数据模型
│   ├── agent/              # 多智能体模块（base.py / supervisor.py 已实现）
│   ├── rag/                # RAG 知识检索模块
│   ├── workflow/           # Agent 工作流
│   ├── data/               # 知识数据（raw / processed / medical）
│   ├── config/             # 配置（settings.py / prompt.py）
│   └── main.py             # 项目入口
├── tests/                  # 测试（pytest）
├── scripts/                # 脚本（chat_demo.py / agent_demo.py）
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

6. 多智能体会诊（Supervisor + 问诊/症状/RAG/风险/专科/回答 6 个子 Agent）：

   ```bash
   # 方式一：终端 Demo（推荐，直观展示完整流程）
   uv run python scripts/agent_demo.py

   # 方式二：HTTP 接口（SSE 事件流，自带 history 参数）
   curl -N -X POST http://localhost:8000/api/agent/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "我最近总是头晕，可能是什么原因？", "history": []}'

   # 方式三：问诊接口（服务端按 session_id 维护多轮历史）
   curl -N -X POST http://localhost:8000/api/consultation \
     -H "Content-Type: application/json" \
     -d '{"message": "我最近肚子疼", "session_id": null}'
   # 从返回的首个事件里拿到 session_id，追问时带上它；查历史：
   curl http://localhost:8000/api/history/<session_id>
   ```

7. RAG 知识检索（向量库 + 重排）：

   ```bash
   # HTTP 接口
   curl -X POST http://localhost:8000/api/knowledge/search \
     -H "Content-Type: application/json" \
     -d '{"query": "高血压的饮食注意事项"}'

   # 终端交互式检索
   uv run python scripts/search_cli.py
   ```

8. 用户注册 / 登录（需 MySQL；见第 10 步）：

   ```bash
   curl -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"username": "测试用户", "password": "abc123456"}'

   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "测试用户", "password": "abc123456"}'
   # 登录成功返回 token；未启动 MySQL 时接口返回 503（其余功能不受影响）
   ```

9. 运行测试（不依赖真实 LLM）：

   ```bash
   uv run pytest tests/ -q
   ```

10. Docker 部署（MySQL + Redis + API）：

    ```bash
    cd docker && docker compose up -d mysql redis
    # 注：容器 MySQL 映射到宿主 3307（本机 3306 常被 Windows 侧 MySQL 占用）
    # .env 里设 MYSQL_ENABLED=1、MYSQL_PORT=3307 后，历史记录和用户数据落库
    # 完整 API 镜像构建：docker compose up -d --build api
    ```

## 开发阶段

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| M1 | 需求分析 | ✅ 已完成（见 RAG医疗v3.md.md） |
| M2 | 基础后端（FastAPI + 基础聊天 API） | ✅ 已完成（含用户注册/登录） |
| M3 | RAG 知识库 | ✅ 已完成（内/外科学第10版，8398 chunks 已入库，检索+重排验证通过） |
| M4 | 单 Agent 医疗咨询 | ✅ 已完成（/api/chat + /api/consultation） |
| M5 | Multi-Agent | ✅ 已完成（问诊/症状/RAG/风险/专科/回答 6 个 Agent） |
| M6 | Agent 协同（Supervisor + LangGraph） | ✅ Supervisor 编排完成（多轮问诊→并行分析→专科→综合回答+知识问答捷径）；LangGraph 未采用：确定性编排已覆盖流程且无状态机需求，重复实现价值低 |
| M7 | 系统整合 | ✅ 已完成（MySQL 持久化：问诊历史/用户数据落库，未启用时自动回退内存；Redis 已就绪） |
| M8 | 测试与优化 | ✅ 已完成（17 项自动化测试全过 + 双流程 E2E 验证） |
| M9 | Docker 部署 | 🚧 compose 已就绪（MySQL/Redis 已验证运行）；API 镜像构建待验证 |
