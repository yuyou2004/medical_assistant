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


# ---------- M9 扩展：真实定位 / 健康数据趋势 / 用药提醒 / FAQ / 体检报告 ----------


@pytest.mark.skipif(not settings.DB_ENABLED, reason="需启用 MySQL（MYSQL_ENABLED=1）")
def test_hospitals_real_location():
    """真实定位：提供经纬度后按 haversine 距离升序，且全部医院带真实坐标"""
    from app.dao import db

    db.init_db()
    r = client.get("/api/hospitals", params={"lat": 30.246, "lng": 120.1645})  # 杭州市一附近
    assert r.status_code == 200
    body = r.json()
    assert body["located"] is True and len(body["hospitals"]) >= 13
    hospitals = body["hospitals"]
    # 距离按真实经纬度计算并升序：最近的三家应都是杭州医院（不再出现深圳医院混排）
    assert all(h["distance_km"] <= hospitals[3]["distance_km"] + 0.01 for h in hospitals[:3])
    assert {h["city"] for h in hospitals[:3]} == {"杭州"}
    assert hospitals[0]["distance_km"] < 10  # 与杭州市中心直线距离在几公里内
    # 全部医院均有真实经纬度
    assert all(h.get("lat") is not None and h.get("lng") is not None for h in hospitals)
    # 不定位时 located=False，返回参考距离
    r2 = client.get("/api/hospitals")
    assert r2.json()["located"] is False


def test_faq_endpoint():
    """FAQ 分类浏览：全量返回分类与问答，按分类过滤生效"""
    r = client.get("/api/faq")
    assert r.status_code == 200
    body = r.json()
    assert len(body["categories"]) >= 5
    assert all(c["count"] >= 3 for c in body["categories"])
    assert len(body["questions"]) >= 15
    r2 = client.get("/api/faq", params={"category": "medication"})
    assert r2.status_code == 200
    med_qs = r2.json()["questions"]
    med_count = next(c["count"] for c in body["categories"] if c["id"] == "medication")
    assert len(med_qs) == med_count >= 3
    assert all("q" in q and "a" in q for q in med_qs)
    r3 = client.get("/api/faq", params={"category": "not-exist"})
    assert r3.json()["questions"] == []


def test_report_requires_input():
    """报告解读：无文本无文件返回 400"""
    r = client.post("/api/report/analyze", data={})
    assert r.status_code == 400


def test_report_image_requires_vision_key():
    """报告图片解读依赖视觉模型 key（本环境未配置 → 503 配置指引）"""
    import io

    r = client.post(
        "/api/report/analyze",
        files={"file": ("report.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")},
    )
    assert r.status_code == 503
    assert "SILICONFLOW_API_KEY" in r.json()["detail"]


@pytest.mark.skipif(not settings.DB_ENABLED, reason="需启用 MySQL（MYSQL_ENABLED=1）")
def test_health_records_flow():
    """健康数据趋势：写入 → 查询（日期升序）→ 最新值 → 删除"""
    from app.dao import db

    db.init_db()
    username = f"测试_{secrets.token_hex(4)}"
    client.post("/api/auth/register", json={"username": username, "password": "pass123456"})
    token = client.post(
        "/api/auth/login", json={"username": username, "password": "pass123456"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 参数校验：类型/数值范围
    assert client.post("/api/health/records", headers=headers,
                       json={"record_type": "height", "value": 70}).status_code == 400
    assert client.post("/api/health/records", headers=headers,
                       json={"record_type": "weight", "value": 9999}).status_code == 400

    r = client.post("/api/health/records", headers=headers,
                    json={"record_type": "weight", "value": 72.5, "note": "晨起空腹"})
    assert r.status_code == 200, r.text
    # 同日期同类型覆盖旧值
    client.post("/api/health/records", headers=headers,
                json={"record_type": "weight", "value": 72.0})
    client.post("/api/health/records", headers=headers,
                json={"record_type": "systolic", "value": 128})

    r = client.get("/api/health/records", headers=headers, params={"record_type": "weight"})
    records = r.json()["records"]
    assert len(records) == 1 and records[0]["value"] == 72.0

    latest = client.get("/api/health/summary", headers=headers).json()["latest"]
    assert latest["weight"]["value"] == 72.0 and latest["systolic"]["value"] == 128

    rid = records[0]["id"]
    assert client.delete(f"/api/health/records/{rid}", headers=headers).status_code == 200
    latest = client.get("/api/health/summary", headers=headers).json()["latest"]
    assert "weight" not in latest and latest["systolic"]["value"] == 128


@pytest.mark.skipif(not settings.DB_ENABLED, reason="需启用 MySQL（MYSQL_ENABLED=1）")
def test_medication_flow():
    """用药提醒：建计划 → 今日清单 → 打卡 → 停用 → 删除"""
    from app.dao import db

    db.init_db()
    username = f"测试_{secrets.token_hex(4)}"
    client.post("/api/auth/register", json={"username": username, "password": "pass123456"})
    token = client.post(
        "/api/auth/login", json={"username": username, "password": "pass123456"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 校验：时间点数量与次数不一致 → 400
    r = client.post("/api/medications", headers=headers, json={
        "medicine_name": "阿莫西林", "times_per_day": 2, "time_points": ["08:00"],
    })
    assert r.status_code == 400

    r = client.post("/api/medications", headers=headers, json={
        "medicine_name": "阿莫西林", "times_per_day": 2,
        "time_points": ["08:00", "20:00"], "note": "饭后服用",
    })
    assert r.status_code == 200, r.text
    med_id = r.json()["medication_id"]

    # 今日清单：2 项均未打卡
    checklist = client.get("/api/medications/checklist/today", headers=headers).json()
    assert checklist["total"] == 2 and checklist["taken"] == 0

    # 打卡：成功；重复打卡幂等；时段不在计划内 → 400
    r = client.post("/api/medications/logs", headers=headers,
                    json={"medication_id": med_id, "time_point": "08:00"})
    assert r.status_code == 200 and r.json()["taken"] == 1
    client.post("/api/medications/logs", headers=headers,
                json={"medication_id": med_id, "time_point": "08:00"})
    checklist = client.get("/api/medications/checklist/today", headers=headers).json()
    assert checklist["taken"] == 1
    assert client.post("/api/medications/logs", headers=headers,
                       json={"medication_id": med_id, "time_point": "12:00"}).status_code == 400

    # 停用后今日清单为空；删除后计划不存在
    r = client.put(f"/api/medications/{med_id}", headers=headers, json={"active": False})
    assert r.status_code == 200
    assert client.get("/api/medications/checklist/today", headers=headers).json()["total"] == 0
    assert client.delete(f"/api/medications/{med_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/medications/{med_id}", headers=headers).status_code == 404
