"""数据库连接与初始化（M7 系统整合）：pymysql 直连 MySQL，简单可靠"""
import json
import logging

import pymysql

from app.config import settings

logger = logging.getLogger(__name__)

# 医院演示种子数据（M8 扩展：附近医院 + 预约挂号；无真实医院系统对接，仅供演示）
# 最后两列为真实经纬度（GCJ-02 附近值，精确到院内区域）；distance_km 为市中心参考距离，
# 用户开启定位后用 haversine 按真实经纬度重算并排序，替换模拟距离。
SEED_HOSPITALS = [
    # 杭州
    ("浙江大学医学院附属第一医院", "三甲", "杭州", "上城区", "上城区庆春路79号", "0571-87236114", ["内科", "外科", "皮肤科", "儿科", "妇产科", "骨科", "眼科", "口腔科", "耳鼻喉科"], 2.1, 4.9, 30.258300, 120.161300),
    ("浙江大学医学院附属第二医院", "三甲", "杭州", "上城区", "上城区解放路88号", "0571-87783777", ["内科", "外科", "皮肤科", "骨科", "眼科", "耳鼻喉科", "中医科"], 3.4, 4.9, 30.247000, 120.162500),
    ("杭州市第一人民医院", "三甲", "杭州", "拱墅区", "拱墅区浣纱路261号", "0571-87910001", ["内科", "外科", "儿科", "妇产科", "皮肤科", "口腔科"], 1.6, 4.7, 30.246000, 120.164500),
    ("杭州市中医院", "三甲", "杭州", "西湖区", "西湖区体育场路453号", "0571-85827888", ["中医科", "内科", "针灸推拿科", "皮肤科", "骨科"], 4.8, 4.6, 30.286000, 120.155500),
    # 北京
    ("北京协和医院", "三甲", "北京", "东城区", "东城区帅府园一号", "010-69156114", ["内科", "外科", "皮肤科", "妇产科", "儿科", "眼科", "耳鼻喉科", "口腔科"], 2.8, 4.9, 39.912100, 116.417200),
    ("北京大学第一医院", "三甲", "北京", "西城区", "西城区西什库大街8号", "010-83572211", ["内科", "外科", "皮肤科", "儿科", "骨科", "中医科"], 3.9, 4.8, 39.929600, 116.385800),
    ("北京同仁医院", "三甲", "北京", "东城区", "东城区东交民巷1号", "010-58269911", ["眼科", "耳鼻喉科", "内科", "外科", "皮肤科"], 4.2, 4.8, 39.901500, 116.412400),
    # 上海
    ("复旦大学附属华山医院", "三甲", "上海", "静安区", "静安区乌鲁木齐中路12号", "021-52889999", ["皮肤科", "神经内科", "内科", "外科", "骨科"], 2.3, 4.9, 31.218800, 121.447100),
    ("上海交通大学医学院附属瑞金医院", "三甲", "上海", "黄浦区", "黄浦区瑞金二路197号", "021-64370045", ["内科", "外科", "皮肤科", "妇产科", "儿科", "眼科"], 3.1, 4.9, 31.208700, 121.466100),
    ("上海市第一人民医院", "三甲", "上海", "虹口区", "虹口区武进路85号", "021-63240090", ["内科", "外科", "眼科", "口腔科", "皮肤科", "中医科"], 4.6, 4.7, 31.250400, 121.480200),
    # 深圳
    ("深圳市人民医院", "三甲", "深圳", "罗湖区", "罗湖区东门北路1017号", "0755-25601111", ["内科", "外科", "儿科", "妇产科", "皮肤科", "口腔科"], 2.7, 4.7, 22.559500, 114.126800),
    ("深圳市第二人民医院", "三甲", "深圳", "福田区", "福田区笋岗西路3002号", "0755-83792459", ["内科", "外科", "骨科", "眼科", "皮肤科", "耳鼻喉科"], 3.3, 4.6, 22.558300, 114.090600),
    ("香港大学深圳医院", "三甲", "深圳", "福田区", "福田区海园一路1号", "0755-86913333", ["内科", "外科", "妇产科", "儿科", "皮肤科", "中医科"], 5.2, 4.8, 22.516600, 114.047500),
]


def _connect(database: str | None) -> pymysql.connections.Connection:
    """新建数据库连接（调用方用完需 close）"""
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=database,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=5,
    )


def get_connection() -> pymysql.connections.Connection:
    """连接到业务库"""
    return _connect(settings.MYSQL_DB)


def init_db() -> bool:
    """建库建表（幂等），成功返回 True；数据库不可用时返回 False 并记日志"""
    if not settings.DB_ENABLED:
        logger.info("MYSQL_ENABLED 未开启，使用内存存储")
        return False
    try:
        # 先不带 database 连接，确保库存在
        conn = _connect(None)
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DB}` "
                "DEFAULT CHARACTER SET utf8mb4"
            )
        conn.close()

        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(128) NOT NULL,
                    salt VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS consultations (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    role VARCHAR(16) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_session (session_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            # M8 扩展：医院 / 预约挂号 / 健康档案
            cur.execute(
                """CREATE TABLE IF NOT EXISTS hospitals (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    level VARCHAR(20) NOT NULL,
                    city VARCHAR(30) NOT NULL,
                    district VARCHAR(30) NOT NULL,
                    address VARCHAR(200) NOT NULL,
                    phone VARCHAR(30) DEFAULT '',
                    departments TEXT NOT NULL,
                    distance_km DECIMAL(5,1) DEFAULT 0,
                    rating DECIMAL(2,1) DEFAULT 4.5,
                    lat DECIMAL(9,6) DEFAULT NULL,
                    lng DECIMAL(9,6) DEFAULT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            # 旧库迁移：hospitals 表补充经纬度列（CREATE TABLE IF NOT EXISTS 不会给已存在的表加列）
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='hospitals' AND COLUMN_NAME='lat'",
                (settings.MYSQL_DB,),
            )
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE hospitals ADD COLUMN lat DECIMAL(9,6) DEFAULT NULL, ADD COLUMN lng DECIMAL(9,6) DEFAULT NULL")
            cur.execute(
                """CREATE TABLE IF NOT EXISTS appointments (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    hospital_name VARCHAR(100) NOT NULL,
                    department VARCHAR(30) NOT NULL,
                    doctor VARCHAR(30) NOT NULL,
                    visit_date DATE NOT NULL,
                    time_slot VARCHAR(20) NOT NULL,
                    patient_name VARCHAR(30) NOT NULL,
                    patient_phone VARCHAR(20) NOT NULL,
                    symptom VARCHAR(500) DEFAULT '',
                    status VARCHAR(16) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_user (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS user_profiles (
                    username VARCHAR(50) PRIMARY KEY,
                    real_name VARCHAR(30) DEFAULT '',
                    gender VARCHAR(10) DEFAULT '',
                    age TINYINT DEFAULT 0,
                    height VARCHAR(10) DEFAULT '',
                    weight VARCHAR(10) DEFAULT '',
                    medical_history TEXT,
                    allergies TEXT,
                    medications TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            # M9 扩展：健康数据趋势 / 用药提醒
            cur.execute(
                """CREATE TABLE IF NOT EXISTS health_records (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    record_type VARCHAR(20) NOT NULL,
                    value DECIMAL(8,2) NOT NULL,
                    note VARCHAR(200) DEFAULT '',
                    record_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_user_type_date (username, record_type, record_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS medications (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    medicine_name VARCHAR(60) NOT NULL,
                    times_per_day TINYINT NOT NULL,
                    time_points TEXT NOT NULL,
                    note VARCHAR(200) DEFAULT '',
                    active TINYINT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    KEY idx_user (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS medication_logs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    medication_id BIGINT NOT NULL,
                    log_date DATE NOT NULL,
                    time_point VARCHAR(5) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_take (medication_id, log_date, time_point)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
            )
            # 医院演示数据（先查重再插入；已存在的行按名称补齐经纬度，保证旧库升级后定位可用）
            cur.execute("SELECT COUNT(*) AS n FROM hospitals")
            if cur.fetchone()[0] == 0:
                for h in SEED_HOSPITALS:
                    cur.execute(
                        "INSERT INTO hospitals "
                        "(name, level, city, district, address, phone, departments, distance_km, rating, lat, lng) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (*h[:6], json.dumps(h[6], ensure_ascii=False), h[7], h[8], h[9], h[10]),
                    )
                logger.info("医院演示数据已写入（%d 家）", len(SEED_HOSPITALS))
            else:
                for h in SEED_HOSPITALS:
                    cur.execute(
                        "UPDATE hospitals SET lat=%s, lng=%s WHERE name=%s AND (lat IS NULL OR lat=0)",
                        (h[9], h[10], h[0]),
                    )
        conn.close()
        logger.info(
            "MySQL 初始化完成：%s@%s:%s/%s",
            settings.MYSQL_USER, settings.MYSQL_HOST, settings.MYSQL_PORT, settings.MYSQL_DB,
        )
        return True
    except Exception:
        logger.exception("MySQL 初始化失败，回退内存存储")
        return False
