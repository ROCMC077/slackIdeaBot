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


# -----------------------------
# 健康檢查（Railway 必須）
# -----------------------------
@app.route("/", methods=["GET"])
def home():
    return "OK", 200


# -----------------------------
# Slack 簽名驗證（可選）
# -----------------------------
def verify_slack_request(req):
    timestamp = req.headers.get("X-Slack-Request-Timestamp")
    slack_signature = req.headers.get("X-Slack-Signature")

    if not timestamp or not slack_signature:
        return False

    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    sig_basestring = f"v0:{timestamp}:{req.get_data(as_text=True)}"
    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(my_signature, slack_signature)


# -----------------------------
# 1. Slash Command：/submit-idea（投稿）
# -----------------------------
@app.route("/submit-idea", methods=["POST"])
def open_idea_form():
    payload = request.form
    trigger_id = payload.get("trigger_id")

    modal = idea_form_modal()

    requests.post(
        "https://slack.com/api/views.open",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"trigger_id": trigger_id, "view": modal},
    )

    return "", 200


# -----------------------------
# 2. Slack Interactions：view_submission（投稿完成）
# -----------------------------
@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():
    raw = request.form.get("payload") or request.get_data(as_text=True)
    payload = json.loads(raw)

    if payload.get("type") == "view_submission":
        values = payload["view"]["state"]["values"]

        # 平台
        platform_block = values.get("platform", {})
        platform_input = platform_block.get("platform_select", {})
        platforms = [opt["value"] for opt in platform_input.get("selected_options", [])]

        # 關鍵字
        keyword_block = values.get("keywords", {})
        keyword_input = keyword_block.get("keyword_select", {})
        keywords = [opt["value"] for opt in keyword_input.get("selected_options", [])]

        # 其它關鍵字
        other_block = values.get("keyword_other", {})
        other_input = other_block.get("keyword_other_input", {})
        other_keyword = other_input.get("value") or ""
        if other_keyword:
            keywords.append(other_keyword)

        # 🔥 連結（支援半形 ":" 與全形 "："）
        links_block = values.get("links", {})
        links_input = links_block.get("links_input", {})
        raw_links = links_input.get("value") or ""

        links = {}
        for line in raw_links.split("\n"):
            line = line.strip()
            if not line:
                continue

            if ":" in line:
                k, v = line.split(":", 1)
            elif "：" in line:
                k, v = line.split("：", 1)
            else:
                continue

            v = v.strip()
            # 修正 Slack 吃掉 https: 的 bug
            if v.startswith("//"):
                v = "https:" + v

            links.setdefault(k.strip(), []).append(v)

        # 補充資訊
        extra_block = values.get("extra_info", {})
        extra_input = extra_block.get("extra_info_input", {})
        extra_info = extra_input.get("value") or ""

        # 寫入資料庫
        idea_id = insert_idea(platforms, keywords, links, extra_info)

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
# 3. Events API：純聊天機器人模式（@Slack Idea Bot）
# -----------------------------
@app.route("/events", methods=["POST"])
def slack_events():
    data = request.get_json(silent=True) or {}

    if "challenge" in data:
        return data["challenge"], 200

    event = data.get("event", {})
    if event.get("type") != "app_mention":
        return "", 200

    text = event.get("text", "") or ""
    channel = event.get("channel")

    if BOT_USER_ID:
        text = text.replace(f"<@{BOT_USER_ID}>", "")
        text = text.replace("\n", "").replace("\r", "").strip()

    # 1. 抽
    if "抽" in text:
        idea = get_random_idea()
        if not idea:
            reply(channel, "目前沒有任何投稿喔！")
        else:
            reply(channel, f"抽到：{idea['idea_id']}\n輸入 IDEA 編號即可查看詳細內容")
        return "", 200

    # 2. 平台查詢
    if is_platform(text):
        ideas = get_ideas_by_platform(text)
        if not ideas:
            reply(channel, f"沒有找到與 {text} 相關的 idea")
        else:
            ids = "\n".join([i["idea_id"] for i in ideas])
            reply(channel, f"{text} 相關的 idea：\n{ids}\n輸入 IDEA 編號即可查看詳細內容")
        return "", 200

    # 3. 關鍵字查詢
    if is_keyword(text):
        ideas = get_ideas_by_keyword(text)
        if not ideas:
            reply(channel, f"沒有找到與 {text} 相關的 idea")
        else:
            ids = "\n".join([i["idea_id"] for i in ideas])
            reply(channel, f"{text} 相關的 idea：\n{ids}\n輸入 IDEA 編號即可查看詳細內容")
        return "", 200

    # 4. 查單一 IDEA
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
        return "", 200

    # 5. 其他輸入
    reply(
        channel,
        "你可以輸入：\n- 抽\n- 平台名稱（Instagram / Facebook / Threads / Reels / Storys / Big idea）\n- 關鍵字（星座 / 節慶 / 借勢 / 諧音 / MBTI / 測驗網 / 短期案 / 殺手鐧 / 貼文大賞 / 遺珠 / 其它）\n- IDEA 編號（例如：IDEA-000001）",
    )
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