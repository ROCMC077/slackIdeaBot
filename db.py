import sqlite3
import json
import os

DB_PATH = "ideas.db"


# -----------------------------
# 初始化資料庫
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idea_id TEXT UNIQUE,
            platforms TEXT,
            keywords TEXT,
            links TEXT,
            extra_info TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# -----------------------------
# 產生自動編號：IDEA-000001
# -----------------------------
def generate_idea_id():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT MAX(id) FROM ideas")
    row = c.fetchone()
    next_id = (row[0] or 0) + 1

    conn.close()
    return f"IDEA-{next_id:06d}"


# -----------------------------
# 新增一筆 Idea
# -----------------------------
def insert_idea(platforms, keywords, links, extra_info):
    idea_id = generate_idea_id()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO ideas (idea_id, platforms, keywords, links, extra_info)
        VALUES (?, ?, ?, ?, ?)
    """, (
        idea_id,
        json.dumps(platforms, ensure_ascii=False),
        json.dumps(keywords, ensure_ascii=False),
        json.dumps(links, ensure_ascii=False),
        extra_info
    ))

    conn.commit()
    conn.close()

    return idea_id


# -----------------------------
# 隨機抽一筆
# -----------------------------
def get_random_idea():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT idea_id FROM ideas ORDER BY RANDOM() LIMIT 1")
    row = c.fetchone()

    conn.close()

    if not row:
        return None

    return {"idea_id": row[0]}


# -----------------------------
# 依平台查詢
# -----------------------------
def get_ideas_by_platform(platform):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT idea_id, platforms FROM ideas")
    rows = c.fetchall()
    conn.close()

    result = []
    for idea_id, platforms_json in rows:
        platforms = json.loads(platforms_json)
        if platform in platforms:
            result.append({"idea_id": idea_id})

    return result


# -----------------------------
# 依關鍵字查詢
# -----------------------------
def get_ideas_by_keyword(keyword):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT idea_id, keywords FROM ideas")
    rows = c.fetchall()
    conn.close()

    result = []
    for idea_id, keywords_json in rows:
        keywords = json.loads(keywords_json)
        if keyword in keywords:
            result.append({"idea_id": idea_id})

    return result


# -----------------------------
# 依編號查詢詳細內容
# -----------------------------
def get_idea_by_id(idea_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT idea_id, platforms, keywords, links, extra_info, created_at
        FROM ideas
        WHERE idea_id = ?
    """, (idea_id,))

    row = c.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "idea_id": row[0],
        "platforms": json.loads(row[1]),
        "keywords": json.loads(row[2]),
        "links": json.loads(row[3]),
        "extra_info": row[4],
        "created_at": row[5]
    }