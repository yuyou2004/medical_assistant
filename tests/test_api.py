"""基础接口测试：不依赖真实 LLM，验证请求校验和服务可用性"""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_root():
    """健康检查可用 + 前端页面托管正常（含三种功能模式入口）"""
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    html = client.get("/")
    assert html.status_code == 200
    assert "多智能体会诊" in html.text and "知识库检索" in html.text


def test_chat_rejects_system_role():
    """history 里不允许出现 system 角色（防提示词注入）"""
    r = client.post(
        "/api/chat",
        json={"message": "你好", "history": [{"role": "system", "content": "x"}]},
    )
    assert r.status_code == 422


def test_chat_rejects_long_message():
    r = client.post("/api/chat", json={"message": "长" * 2001})
    assert r.status_code == 422


def test_chat_rejects_empty_message():
    r = client.post("/api/chat", json={"message": ""})
    assert r.status_code == 422


def test_chat_rejects_too_much_history():
    history = [{"role": "user", "content": "x"}] * 21
    r = client.post("/api/chat", json={"message": "你好", "history": history})
    assert r.status_code == 422


def test_agent_rejects_system_role():
    """智能体接口同样不允许 system 角色"""
    r = client.post(
        "/api/agent/chat",
        json={"message": "你好", "history": [{"role": "system", "content": "x"}]},
    )
    assert r.status_code == 422


def test_agent_rejects_long_message():
    r = client.post("/api/agent/chat", json={"message": "长" * 2001})
    assert r.status_code == 422


def test_consultation_rejects_empty_message():
    r = client.post("/api/consultation", json={"message": ""})
    assert r.status_code == 422


def test_knowledge_search_rejects_empty_query():
    r = client.post("/api/knowledge/search", json={"query": ""})
    assert r.status_code == 422


def test_history_not_found():
    r = client.get("/api/history/not-exist-session")
    assert r.status_code == 404


def test_sessions_empty():
    r = client.get("/api/sessions")
    assert r.status_code == 200
    assert "sessions" in r.json()


def test_agent_registry_has_all_agents():
    """启动后注册表应包含 Supervisor + 6 个子 Agent"""
    from app.agent import list_agents, setup_default_agents

    setup_default_agents()
    names = set(list_agents().keys())
    assert {"supervisor", "inquiry", "symptom", "rag", "risk", "specialty", "answer"} <= names


def test_red_flag_detection():
    """危险信号关键词硬规则：普通症状不命中，急症表现必命中"""
    from app.agent.risk_agent import RiskAgent

    assert RiskAgent.check_red_flags("我最近有点咳嗽，晚上比较严重") == []
    flags = RiskAgent.check_red_flags("我突然剧烈胸痛，还呼吸困难")
    assert "剧烈胸痛" in flags and "呼吸困难" in flags


def test_knowledge_stats_endpoint():
    """知识库状态接口可用（未建库时 chunk 数为 0，不报错）"""
    r = client.get("/api/knowledge/stats")
    assert r.status_code == 200
    body = r.json()
    assert "chunk_count" in body and isinstance(body["pdfs"], list)


# ---------- 用户认证与持久化（依赖 MySQL；未启用时自动跳过） ----------


def test_auth_register_validation():
    """注册参数校验：用户名/密码长度不足返回 422（不依赖数据库）"""
    r = client.post("/api/auth/register", json={"username": "a", "password": "123456"})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={"username": "张三", "password": "123"})
    assert r.status_code == 422


@pytest.mark.skipif(not settings.DB_ENABLED, reason="需启用 MySQL（MYSQL_ENABLED=1）")
def test_auth_register_login_flow():
    """注册 → 重复注册 400 → 错误密码 401 → 登录成功返回 token"""
    from app.dao import db

    db.init_db()  # TestClient 未走 lifespan，这里显式建表（幂等）
    username = f"测试_{secrets.token_hex(4)}"
    r = client.post(
        "/api/auth/register", json={"username": username, "password": "pass123456"}
    )
    assert r.status_code == 200, r.text
    r = client.post(
        "/api/auth/register", json={"username": username, "password": "pass123456"}
    )
    assert r.status_code == 400
    r = client.post(
        "/api/auth/login", json={"username": username, "password": "wrong-password"}
    )
    assert r.status_code == 401
    r = client.post(
        "/api/auth/login", json={"username": username, "password": "pass123456"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"] and body["username"] == username


@pytest.mark.skipif(not settings.DB_ENABLED, reason="需启用 MySQL（MYSQL_ENABLED=1）")
def test_auth_me_and_logout():
    """注册 → 登录 → /me 校验 → 退出 → /me 返回 401"""
    from app.dao import db

    db.init_db()
    username = f"测试_{secrets.token_hex(4)}"
    client.post("/api/auth/register", json={"username": username, "password": "pass123456"})
    token = client.post(
        "/api/auth/login", json={"username": username, "password": "pass123456"}
    ).json()["token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["username"] == username
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.skipif(not settings.DB_ENABLED, reason="需启用 MySQL（MYSQL_ENABLED=1）")
def test_hospitals_and_schedule():
    """医院演示数据可用 + 排班确定性生成（M8 扩展）"""
    from app.dao import db

    db.init_db()
    r = client.get("/api/hospitals", params={"city": "杭州"})
    assert r.status_code == 200
    body = r.json()
    assert body["demo"] and len(body["hospitals"]) >= 3
    hid = body["hospitals"][0]["id"]
    # 排班：7 天、含余号，且两次调用结果一致（确定性）
    s1 = client.get("/api/hospitals/schedule", params={"hospital_id": hid, "department": "皮肤科"}).json()
    s2 = client.get("/api/hospitals/schedule", params={"hospital_id": hid, "department": "皮肤科"}).json()
    assert len(s1["dates"]) == 7 and s1["slots"] == s2["slots"]
    assert s1["slots"][s1["dates"][0]][s1["time_slots"][0]]


def test_vision_requires_key():
    """未配置视觉模型 key 时，图片问诊返回 503 并给出配置指引"""
    import io

    r = client.post(
        "/api/vision/analyze",
        files={"file": ("test.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")},
    )
    assert r.status_code == 503
    assert "SILICONFLOW_API_KEY" in r.json()["detail"]


def test_profile_requires_login():
    """健康档案接口需登录"""
    assert client.get("/api/profile").status_code == 401
    assert client.put("/api/profile", json={}).status_code == 401


@pytest.mark.skipif(not settings.DB_ENABLED, reason="需启用 MySQL（MYSQL_ENABLED=1）")
def test_appointment_flow():
    """预约挂号全流程：查排班 → 预约 → 我的预约 → 取消（M8 扩展）"""
    import json

    from app.dao import db

    db.init_db()
    username = f"测试_{secrets.token_hex(4)}"
    client.post("/api/auth/register", json={"username": username, "password": "pass123456"})
    token = client.post(
        "/api/auth/login", json={"username": username, "password": "pass123456"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    hospitals = client.get("/api/hospitals").json()["hospitals"]
    hospital = next(h for h in hospitals if "皮肤科" in h["departments"])
    sched = client.get(
        "/api/hospitals/schedule", params={"hospital_id": hospital["id"], "department": "皮肤科"}
    ).json()
    # 找一个有余号的 医生+日期+时段 组合（确定性生成，稳定可复现）
    picked = None
    for d in sched["dates"]:
        for slot in sched["time_slots"]:
            for doctor, remaining in sched["slots"][d][slot].items():
                if remaining > 0:
                    picked = (d, slot, doctor)
                    break
            if picked: break
        if picked: break
    assert picked, "排班中应存在余号"
    d, slot, doctor = picked

    r = client.post("/api/appointments", headers=headers, json={
        "hospital_id": hospital["id"], "department": "皮肤科", "doctor": doctor,
        "visit_date": d, "time_slot": slot,
        "patient_name": "测试患者", "patient_phone": "13800138000", "symptom": "皮肤瘙痒",
    })
    assert r.status_code == 200, r.text
    aid = r.json()["appointment_id"]

    r = client.get("/api/appointments", headers=headers)
    assert r.status_code == 200
    assert any(a["id"] == aid and a["status"] == "active" for a in r.json()["appointments"])

    r = client.delete(f"/api/appointments/{aid}", headers=headers)
    assert r.status_code == 200
    r = client.get("/api/appointments", headers=headers)
    assert any(a["id"] == aid and a["status"] == "cancelled" for a in r.json()["appointments"])


@pytest.mark.skipif(not settings.DB_ENABLED, reason="需启用 MySQL（MYSQL_ENABLED=1）")
def test_consultation_dao_persists():
    """问诊消息写入 MySQL 后可读回"""
    from uuid import uuid4

    from app.dao import consultation_dao, db

    db.init_db()  # TestClient 未走 lifespan，这里显式建表（幂等）
    sid = f"test-{uuid4().hex}"
    consultation_dao.save_message(sid, "user", "我头疼")
    messages = consultation_dao.load_messages(sid)
    assert messages and {"role": "user", "content": "我头疼"} in messages
