import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime

# 連線字串（Railway 會自動提供 DATABASE_URL）
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


# -----------------------------
# 建立資料表（PostgreSQL）
# -----------------------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id SERIAL PRIMARY KEY,
            idea_id TEXT UNIQUE,
            platforms JSONB,
            keywords JSONB,
            links JSONB,
            extra_info TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


# -----------------------------
# 產生 IDEA-000001 這種編號
# -----------------------------
def generate_idea_id(cur):
    cur.execute("SELECT COUNT(*) FROM ideas;")
    count = cur.fetchone()[0] + 1
    return f"IDEA-{count:06d}"


# -----------------------------
# 新增一筆 idea
# -----------------------------
def insert_idea(platforms, keywords, links, extra_info):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    idea_id = generate_idea_id(cur)

    cur.execute("""
        INSERT INTO ideas (idea_id, platforms, keywords, links, extra_info)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING idea_id;
    """, (
        idea_id,
        json.dumps(platforms),
        json.dumps(keywords),
        json.dumps(links),
        extra_info
    ))

    conn.commit()
    cur.close()
    conn.close()

    return idea_id


# -----------------------------
# 隨機抽一筆
# -----------------------------
def get_random_idea():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT * FROM ideas
        ORDER BY RANDOM()
        LIMIT 1;
    """)

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return None

    # JSONB 自動轉 dict，不用 loads
    return row


# -----------------------------
# 依平台查詢
# -----------------------------
def get_ideas_by_platform(platform):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT idea_id FROM ideas
        WHERE platforms @> %s::jsonb;
    """, (json.dumps([platform]),))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return rows


# -----------------------------
# 依關鍵字查詢
# -----------------------------
def get_ideas_by_keyword(keyword):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT idea_id FROM ideas
        WHERE keywords @> %s::jsonb;
    """, (json.dumps([keyword]),))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return rows


# -----------------------------
# 查單一 IDEA
# -----------------------------
def get_idea_by_id(idea_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT * FROM ideas
        WHERE idea_id = %s;
    """, (idea_id,))

    row = cur.fetchone()
    cur.close()
    conn.close()

    return row