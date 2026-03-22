import os
import json
import time
import hmac
import hashlib
import requests
from flask import Flask, request, jsonify
from config import SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET
from blockkit import idea_form_modal, idea_detail_block
from db import (
    init_db,
    insert_idea,
    get_random_idea,
    get_ideas_by_platform,
    get_ideas_by_keyword,
    get_idea_by_id,
)
from query import is_platform, is_keyword

app = Flask(__name__)

# 初始化資料庫
init_db()

SLACK_API_URL = "https://slack.com/api/chat.postMessage"
BOT_USER_ID = os.environ.get("BOT_USER_ID")


@app.route("/", methods=["GET"])
def home():
    return "OK", 200


# -----------------------------
# 共用查詢邏輯（DM + @bot 都會用）
# -----------------------------
def handle_query(text, channel):

    # 抽
    if "抽" in text:
        idea = get_random_idea()
        if not idea:
            reply(channel, "目前沒有任何投稿喔！")
        else:
            reply(channel, f"抽到：{idea['idea_id']}\n輸入 IDEA 編號即可查看詳細內容")
        return ""

    # 平台查詢
    if is_platform(text):
        ideas = get_ideas_by_platform(text)
        if not ideas:
            reply(channel, f"沒有找到與 {text} 相關的 idea")
        else:
            ids = "\n".join([i["idea_id"] for i in ideas])
            reply(channel, f"{text} 相關的 idea：\n{ids}\n輸入 IDEA 編號即可查看詳細內容")
        return ""

    # 關鍵字查詢
    if is_keyword(text):
        ideas = get_ideas_by_keyword(text)
        if not ideas:
            reply(channel, f"沒有找到與 {text} 相關的 idea")
        else:
            ids = "\n".join([i["idea_id"] for i in ideas])
            reply(channel, f"{text} 相關的 idea：\n{ids}\n輸入 IDEA 編號即可查看詳細內容")
        return ""

    # IDEA 編號查詢
    if text.startswith("IDEA-"):
        idea = get_idea_by_id(text)
        if not idea:
            reply(channel, "查無此編號")
        else:
            block = idea_detail_block(idea)
            requests.post(
                SLACK_API_URL,
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json={"channel": channel, "blocks": block},
            )
        return ""

    # fallback
    reply(
        channel,
        "你可以輸入：\n- 抽\n- 平台名稱（Instagram / Facebook / Threads / Reels / Storys / Big idea）\n- 關鍵字（星座 / 節慶 / 借勢 / 諧音 / MBTI / 測驗網 / 短期案 / 殺手鐧 / 貼文大賞 / 遺珠 / 其它）\n- IDEA 編號（例如：IDEA-000001）",
    )
    return ""


# -----------------------------
# Events API：支援 DM + @bot
# -----------------------------
@app.route("/events", methods=["POST"])
def slack_events():
    data = request.get_json(silent=True) or {}

    # Slack URL 驗證
    if "challenge" in data:
        return data["challenge"], 200

    event = data.get("event", {})
    event_type = event.get("type")
    channel_type = event.get("channel_type")
    text = event.get("text", "") or ""
    channel = event.get("channel")

    # -----------------------------
    # 1. DM 模式（message.im）
    # -----------------------------
    if event_type == "message" and channel_type == "im":
        text = text.strip()
        return handle_query(text, channel)

    # -----------------------------
    # 2. @bot 模式（app_mention）
    # -----------------------------
    if event_type == "app_mention":
        if BOT_USER_ID:
            text = text.replace(f"<@{BOT_USER_ID}>", "")
            text = text.replace("\n", "").replace("\r", "").strip()
        return handle_query(text, channel)

    return "", 200


# -----------------------------
# Slack 回覆訊息（純文字）
# -----------------------------
def reply(channel, text):
    requests.post(
        SLACK_API_URL,
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": text},
    )


# -----------------------------
# 啟動 Flask（Railway 必須）
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)