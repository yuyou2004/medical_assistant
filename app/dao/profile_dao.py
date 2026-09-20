"""健康档案数据访问（M8 扩展）：用户病史/过敏史等（会诊时自动携带）"""
import json

from app.dao import db

EMPTY_PROFILE = {
    "real_name": "", "gender": "", "age": 0,
    "height": "", "weight": "",
    "medical_history": [], "allergies": [], "medications": [],
}


def _row_to_profile(row) -> dict:
    def to_list(v):
        try:
            data = json.loads(v)
            return data if isinstance(data, list) else []
        except Exception:
            return [x.strip() for x in str(v).split(",") if x.strip()] if v else []

    return {
        "real_name": row[1] or "", "gender": row[2] or "", "age": row[3] or 0,
        "height": row[4] or "", "weight": row[5] or "",
        "medical_history": to_list(row[6]),
        "allergies": to_list(row[7]),
        "medications": to_list(row[8]),
    }


def get_profile(username: str) -> dict:
    """读取档案，无记录返回空档案"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, real_name, gender, age, height, weight, "
                "medical_history, allergies, medications FROM user_profiles WHERE username=%s",
                (username,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return _row_to_profile(row) if row else dict(EMPTY_PROFILE)


def upsert_profile(username: str, profile: dict) -> None:
    """创建或更新档案（列表字段存 JSON）"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_profiles (username, real_name, gender, age, height, weight, "
                "medical_history, allergies, medications) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE real_name=VALUES(real_name), gender=VALUES(gender), "
                "age=VALUES(age), height=VALUES(height), weight=VALUES(weight), "
                "medical_history=VALUES(medical_history), allergies=VALUES(allergies), "
                "medications=VALUES(medications)",
                (
                    username,
                    profile.get("real_name", ""),
                    profile.get("gender", ""),
                    int(profile.get("age") or 0),
                    profile.get("height", ""),
                    profile.get("weight", ""),
                    json.dumps(profile.get("medical_history", []), ensure_ascii=False),
                    json.dumps(profile.get("allergies", []), ensure_ascii=False),
                    json.dumps(profile.get("medications", []), ensure_ascii=False),
                ),
            )
    finally:
        conn.close()


def format_profile(profile: dict) -> str:
    """档案转成给大模型的上下文片段"""
    parts = []
    if profile.get("real_name"):
        parts.append(f"姓名：{profile['real_name']}")
    if profile.get("gender"):
        parts.append(f"性别：{profile['gender']}")
    if profile.get("age"):
        parts.append(f"年龄：{profile['age']}")
    if profile.get("height") or profile.get("weight"):
        parts.append(f"身高体重：{profile.get('height', '?')}cm / {profile.get('weight', '?')}kg")
    if profile.get("medical_history"):
        parts.append("既往病史：" + "、".join(profile["medical_history"]))
    if profile.get("allergies"):
        parts.append("过敏史：" + "、".join(profile["allergies"]))
    if profile.get("medications"):
        parts.append("正在用药：" + "、".join(profile["medications"]))
    return "\n".join(parts)
