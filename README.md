# 多智能体协同 RAG 医疗咨询助手

基于大语言模型 + RAG + Multi-Agent 的 AI 智能问诊辅助系统。完整设计见 [RAG医疗v3.md.md](RAG医疗v3.md.md)。

## 目录结构

```text
medical_assistant/
├── app/                    # 应用代码
│   ├── api/                # API 接口层（chat / agent / knowledge / auth / hospital /
│   │                       #   appointment / profile / vision / report / faq / health / medication）
│   ├── service/            # 业务逻辑层（chat_service.py / llm_service.py 已实现）
│   ├── dao/                # 数据访问层（db / hospital / health / medication 等）
│   ├── model/              # 数据模型
│   ├── agent/              # 多智能体模块（supervisor + 6 个子 Agent）
│   ├── rag/                # RAG 知识检索模块
│   ├── workflow/           # Agent 工作流
│   ├── data/               # 知识数据（raw / processed / medical）
│   ├── config/             # 配置（settings.py / prompt.py）
│   └── main.py             # 项目入口
├── frontend/               # 前端页面（index.html 主界面 / login.html 登录，后端同源托管）
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

4. 打开 Web 界面（前端页面由后端同源托管，无需单独部署）：

   ```
   http://localhost:8000/           # 首页：问候语 + 快捷提问 + 统计 + 功能网格
   http://localhost:8000/login.html # 登录注册（也可访客身份进入）
   ```

   首页提供快捷提问框与功能网格，全部 11 个功能同时收在右上角"功能"下拉菜单，分四组：
   - 智能咨询：智能问答（大模型直接回答）、多智能体会诊（Supervisor + 6 Agent，会诊过程实时可视化：阶段时间线 / 三路并行分析 / RAG 检索详情 / 风险徽章 / 文献来源 / 问诊追问）、知识库检索（教材原文片段 + 精确页码）
   - 医疗服务：预约挂号（选科室→医院排班→挂号单→我的预约，需登录）、附近医院（浏览器真实定位，按直线距离"离我最近"排序）、图片问诊（上传皮肤照片，视觉大模型识别；需 SILICONFLOW_API_KEY）、体检报告解读（文本/图片逐项解读，输出指标评估与建议）
   - 健康管理：健康档案（病史/过敏史，会诊时自动携带）、健康数据趋势（体重/血压记录 + 折线图，7/30/90 天范围）、用药提醒（用药计划 + 打卡清单 + 浏览器到点通知）
   - 就医指南：常见问题（预约/检查/用药/就医流程分类问答）

5. 测试聊天接口（SSE 流式输出）：

   ```bash
   curl -N -X POST http://localhost:8000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "最近总是睡不好怎么办？"}'
   ```

   接口文档：http://localhost:8000/docs

6. 终端聊天 Demo（不启动 Web 服务，直接输入、流式输出）：

   ```bash
   uv run python scripts/chat_demo.py
   ```

7. 多智能体会诊（Supervisor + 问诊/症状/RAG/风险/专科/回答 6 个子 Agent）：

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

8. RAG 知识检索（向量库 + 重排）：

   ```bash
   # HTTP 接口
   curl -X POST http://localhost:8000/api/knowledge/search \
     -H "Content-Type: application/json" \
     -d '{"query": "高血压的饮食注意事项"}'

   # 终端交互式检索
   uv run python scripts/search_cli.py
   ```

9. 用户注册 / 登录（需 MySQL；见第 14 步）：

   ```bash
   curl -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"username": "测试用户", "password": "abc123456"}'

   curl -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "测试用户", "password": "abc123456"}'
   # 登录成功返回 token；未启动 MySQL 时接口返回 503（其余功能不受影响）
   # 携带 token 的接口：GET /api/auth/me、POST /api/auth/logout、预约/档案接口
   ```

10. 医疗服务 API（M9 扩展：预约挂号 / 附近医院 / 健康档案）：

   ```bash
   TOKEN=<登录返回的 token>

   # 附近医院（13 家演示医院带真实经纬度，可按城市/区/科室筛选）
   curl "http://localhost:8000/api/hospitals?city=杭州&department=皮肤科"
   # 真实定位：传入经纬度后按 haversine 直线距离升序，返回 located=true
   curl "http://localhost:8000/api/hospitals?lat=30.246&lng=120.1645"

   # 挂号排班（未来 7 天，余号确定性生成）
   curl "http://localhost:8000/api/hospitals/schedule?hospital_id=1&department=皮肤科"

   # 预约挂号（需登录）
   curl -X POST http://localhost:8000/api/appointments \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"hospital_id": 1, "department": "皮肤科", "doctor": "王慧",
          "visit_date": "2026-09-21", "time_slot": "10:00-12:00",
          "patient_name": "张三", "patient_phone": "13800138000", "symptom": "皮疹"}'
   curl http://localhost:8000/api/appointments -H "Authorization: Bearer $TOKEN"   # 我的预约
   curl -X DELETE http://localhost:8000/api/appointments/1 -H "Authorization: Bearer $TOKEN"  # 取消

   # 健康档案（需登录；多智能体会诊传 include_profile=true 时自动携带）
   curl -X PUT http://localhost:8000/api/profile \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"real_name": "张三", "gender": "男", "age": 30,
          "medical_history": ["高血压"], "allergies": ["青霉素"], "medications": []}'
   curl http://localhost:8000/api/profile/summary -H "Authorization: Bearer $TOKEN"
   ```

11. 图片问诊（视觉大模型，需 SiliconFlow Key）：

    ```bash
    # .env 配置（硅基流动官网免费申请，同一个 key 同时启用重排）：
    #   SILICONFLOW_API_KEY=sk-xxx
    curl -X POST http://localhost:8000/api/vision/analyze \
      -F "file=@皮肤照片.jpg"
    # 未配置 key 时返回 503 与配置指引，其余功能不受影响
    ```

12. M10 扩展 API（体检报告解读 / 用药提醒 / 健康数据趋势 / FAQ）：

    ```bash
    # 体检报告解读（文本直接传参；图片走视觉模型 OCR，需 SILICONFLOW_API_KEY）
    curl -X POST http://localhost:8000/api/report/analyze \
      -H "Content-Type: application/json" \
      -d '{"text": "谷丙转氨酶 45 U/L，参考范围 9-50；总胆固醇 6.2 mmol/L，参考 3.1-5.7"}'
    curl -X POST http://localhost:8000/api/report/analyze -F "file=@体检报告.jpg"

    # 健康数据趋势（需登录；record_type: weight / systolic / diastolic，同日期同类型覆盖旧值）
    curl -X POST http://localhost:8000/api/health/records \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d '{"record_type": "weight", "value": 72.5, "note": "晨起空腹"}'
    curl "http://localhost:8000/api/health/records?record_type=weight&days=30" -H "Authorization: Bearer $TOKEN"
    curl http://localhost:8000/api/health/summary -H "Authorization: Bearer $TOKEN"   # 各指标最新值
    curl -X DELETE http://localhost:8000/api/health/records/1 -H "Authorization: Bearer $TOKEN"

    # 用药提醒（需登录；time_points 数量需与 times_per_day 一致）
    curl -X POST http://localhost:8000/api/medications \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d '{"medicine_name": "阿莫西林", "times_per_day": 2,
           "time_points": ["08:00", "20:00"], "note": "饭后服用"}'
    curl http://localhost:8000/api/medications/checklist/today -H "Authorization: Bearer $TOKEN"  # 今日清单
    curl -X POST http://localhost:8000/api/medications/logs \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d '{"medication_id": 1, "time_point": "08:00"}'   # 打卡（幂等）

    # 常见问题 FAQ（分类浏览，无需登录）
    curl http://localhost:8000/api/faq
    curl "http://localhost:8000/api/faq?category=medication"
    ```

    用药提醒的前端到点通知基于浏览器 Notification API（页面打开时每 30 秒检查一次到点计划）；
    生产环境如需后台定时推送，可在 Redis 就绪后加 Celery/APScheduler 定时任务。

13. 运行测试（不依赖真实 LLM）：

    ```bash
    uv run pytest tests/ -q
    ```

14. Docker 部署（MySQL + Redis + API）：

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
| M8 | 测试与优化 | ✅ 已完成（28 项自动化测试全过 + 三模式双流程 E2E 验证） |
| M9 | 医疗服务扩展 | ✅ 已完成（预约挂号、附近医院、图片问诊、健康档案，前后端+MySQL 全链路） |
| M10 | 五项功能扩展 | ✅ 已完成（体检报告解读、用药提醒、健康数据趋势、真实地理定位、FAQ；首页改版 + 右上角功能菜单 + 启动速度优化 60s→8s） |
| M11 | Docker 部署 | 🚧 compose 已就绪（MySQL/Redis 已验证运行）；API 镜像构建待验证 |
