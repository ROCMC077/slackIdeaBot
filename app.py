import os
import json
import sqlite3
from flask import Flask, request, jsonify, make_response
from config import SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET
from blockkit import idea_form_modal, idea_detail_block
from db import init_db, insert_idea, get_random_idea, get_ideas_by_platform, get_ideas_by_keyword, get_idea_by_id
from query import is_platform, is_keyword
import hashlib
import hmac
import time
import requests

app = Flask(__name__)

# 初始化資料庫
init_db()

SLACK_API_URL = "https://slack.com/api/chat.postMessage"


# -----------------------------
# 健康檢查（Railway 必須）
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    return "OK", 200


# -----------------------------
# Slack 驗證簽名（可選）
# -----------------------------
def verify_slack_request(req):
    timestamp = req.headers.get("X-Slack-Request-Timestamp")
    slack_signature = req.headers.get("X-Slack-Signature")

    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}"
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(my_signature, slack_signature)


# -----------------------------
# 1. Slash Command：/submit-idea
# -----------------------------
@app.route("/submit-idea", methods=["POST"])
def open_idea_form():
    payload = request.form
    trigger_id = payload.get("trigger_id")

    modal = idea_form_modal()

    requests.post(
        "https://slack.com/api/views.open",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"trigger_id": trigger_id, "view": modal}
    )

    return "", 200


# -----------------------------
# 2. Slack Interactions：view_submission
# -----------------------------
@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():
    # Slack 有時候用 form-data，有時候用 JSON
    raw = request.form.get("payload")
    if not raw:
        raw = request.get_data(as_text=True)

    payload = json.loads(raw)

    # 處理 modal 提交
    if payload["type"] == "view_submission":
        state = payload["view"]["state"]["values"]

        # 平台
        platforms = [
            opt["value"]
            for opt in state["platform"]["platform_select"].get("selected_options", [])
        ]

        # 關鍵字
        keywords = [
            opt["value"]
            for opt in state["keywords"]["keyword_select"].get("selected_options", [])
        ]

        # 其他關鍵字
        other_keyword = state["keyword_other"]["keyword_other_input"].get("value") or ""
        if other_keyword:
            keywords.append(other_keyword)

        # 連結（可能為 None）
        raw_links = state["links"]["links_input"].get("value") or ""
        links = {}
        for line in raw_links.split("\n"):
            if "：" in line:
                k, v = line.split("：", 1)
                links.setdefault(k.strip(), []).append(v.strip())

        # 補充資訊
        extra_info = state["extra_info"]["extra_info_input"].get("value") or ""

        # 寫入資料庫
        idea_id = insert_idea(platforms, keywords, links, extra_info)

        # 回傳成功 modal
        return jsonify({
            "response_action": "update",
            "view": {
                "type": "modal",
                "title": {"type": "plain_text", "text": "投稿成功"},
                "close": {"type": "plain_text", "text": "關閉"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"你的 Idea 已成功投稿！\n編號：*{idea_id}*"
                        }
                    }
                ]
            }
        })

    return "", 200


# -----------------------------
# 3. Events API：抽、查詢、查看詳細
# -----------------------------
@app.route("/events", methods=["POST"])
def slack_events():

    # Slack URL 驗證（x-www-form-urlencoded）
    if request.headers.get("Content-Type") == "application/x-www-form-urlencoded":
        form = request.form
        if "challenge" in form:
            return form["challenge"], 200

    # 其他事件（JSON）
    data = request.get_json(silent=True) or {}

    if "challenge" in data:
        return data["challenge"], 200

    event = data.get("event", {})
    text = event.get("text", "")
    channel = event.get("channel")

    # 抽
    if "抽" in text:
        idea = get_random_idea()
        if not idea:
            reply(channel, "目前沒有任何投稿喔！")
        else:
            reply(channel, f"抽到：{idea['idea_id']}\n輸入編號即可查看詳細內容")
        return "", 200

    # 平台查詢
    if is_platform(text):
        ideas = get_ideas_by_platform(text)
        if not ideas:
            reply(channel, f"沒有找到與 {text} 相關的 idea")
        else:
            ids = "\n".join([i["idea_id"] for i in ideas])
            reply(channel, f"{text} 相關的 idea：\n{ids}\n輸入編號即可查看詳細內容")
        return "", 200

    # 關鍵字查詢
    if is_keyword(text):
        ideas = get_ideas_by_keyword(text)
        if not ideas:
            reply(channel, f"沒有找到與 {text} 相關的 idea")
        else:
            ids = "\n".join([i["idea_id"] for i in ideas])
            reply(channel, f"{text} 相關的 idea：\n{ids}\n輸入編號即可查看詳細內容")
        return "", 200

    # 查看詳細（IDEA-000123）
    if text.startswith("IDEA-"):
        idea = get_idea_by_id(text)
        if not idea:
            reply(channel, "查無此編號")
        else:
            block = idea_detail_block(idea)
            requests.post(
                SLACK_API_URL,
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json={"channel": channel, "blocks": block}
            )
        return "", 200

    return "", 200


# -----------------------------
# Slack 回覆訊息
# -----------------------------
def reply(channel, text):
    requests.post(
        SLACK_API_URL,
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": text}
    )


# -----------------------------
# 啟動 Flask（Railway 必須）
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)