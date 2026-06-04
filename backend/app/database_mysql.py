"""MySQL 数据库连接层 — 用于 LMS 业务表（req_documents / generated_issues / feedbacks 等）。

与 database.py（SQLite，用于考试/成绩）完全隔离，通过独立的上下文管理器 db() 访问。
"""

import os
import pymysql
from contextlib import contextmanager

MYSQL_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "156.239.252.40"),
    "port": int(os.environ.get("MYSQL_PORT", "13306")),
    "user": os.environ.get("MYSQL_USER", "student_dev"),
    "password": os.environ.get("MYSQL_PASSWORD", "OaEpp@Dev2026"),
    "database": os.environ.get("MYSQL_DATABASE", "oaepp_dev"),
    "charset": "utf8mb4",
    "connect_timeout": 10,
    "read_timeout": 30,
    "write_timeout": 30,
}


def get_connection():
    """创建 MySQL 连接（DictCursor 返回字典格式行）。"""
    return pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **MYSQL_CONFIG)


@contextmanager
def db():
    """MySQL 数据库上下文管理器，自动 commit/rollback/close。

    用法:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT ...", params)
            rows = cur.fetchall()   # 每行是 dict
    """
    conn = None
    try:
        conn = get_connection()
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def check_mysql_connection() -> bool:
    """启动时检测 MySQL 是否可达，返回 True/False 不抛异常。"""
    try:
        conn = get_connection()
        conn.close()
        return True
    except Exception:
        return False
