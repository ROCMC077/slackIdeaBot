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

# Slack API
SLACK_API_URL = "https://slack.com/api/chat.postMessage"


# -----------------------------
# Slack 驗證簽名
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
# 1. Slash Command：/submit-idea → 打開 Block Kit Modal
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
# 2. Slack Interactions：接收 view_submission
# -----------------------------
@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():
    payload = json.loads(request.form["payload"])

    if payload["type"] == "view_submission":
        state = payload["view"]["state"]["values"]

        # 解析平台（多選）
        platforms = [opt["value"] for opt in state["platform"]["platform_select"]["selected_options"]]

        # 解析關鍵字（多選）
        keywords = [opt["value"] for opt in state["keywords"]["keyword_select"]["selected_options"]]

        # 若選其它 → 加入填寫內容
        other_keyword = state["keyword_other"]["keyword_other_input"].get("value")
        if other_keyword:
            keywords.append(other_keyword)

        # 解析連結（多筆）
        raw_links = state["links"]["links_input"].get("value", "")
        links = {}
        for line in raw_links.split("\n"):
            if "：" in line:
                k, v = line.split("：", 1)
                links.setdefault(k.strip(), []).append(v.strip())

        # 補充資訊
        extra_info = state["extra_info"]["extra_info_input"].get("value", "")

        # 存資料庫
        idea_id = insert_idea(platforms, keywords, links, extra_info)

        # 回覆 Slack
        return {
            "response_action": "update",
            "view": {
                "type": "modal",
                "title": {"type": "plain_text", "text": "投稿成功"},
                "close": {"type": "plain_text", "text": "關閉"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"你的 Idea 已成功投稿！\n編號：*{idea_id}*"}
                    }
                ]
            }
        }

    return "", 200


# -----------------------------
# 3. Events API：抽、查詢、查看詳細
# -----------------------------
@app.route("/events", methods=["POST"])
def slack_events():
    data = request.json

    # Slack URL 驗證
    if "challenge" in data:
        return make_response(data["challenge"], 200)

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

    # 查看詳細（輸入 IDEA-000123）
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
# 啟動 Flask
# -----------------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)