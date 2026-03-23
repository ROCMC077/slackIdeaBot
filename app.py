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
BOT_USER_ID = os.environ.get("BOT_USER_ID")  # Bot user id，例如：U12345678


@app.route("/", methods=["GET"])
def home():
    return "OK", 200


# -----------------------------
# Slack request 驗證（建議保留）
# -----------------------------
def verify_slack_request(req):
    timestamp = req.headers.get("X-Slack-Request-Timestamp")
    slack_signature = req.headers.get("X-Slack-Signature")

    if not timestamp or not slack_signature:
        return False

    # 避免 replay attack
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    body = req.get_data(as_text=True)  # raw body
    sig_basestring = f"v0:{timestamp}:{body}"

    my_signature = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(my_signature, slack_signature)


# -----------------------------
# Slack 回覆訊息（純文字）
# -----------------------------
def reply(channel, text):
    requests.post(
        SLACK_API_URL,
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": text},
        timeout=10,
    )


# -----------------------------
# 共用查詢邏輯（DM + @bot）
# -----------------------------
def handle_query(text, channel):
    text = (text or "").strip()

    # 抽
    if "抽" in text:
        idea = get_random_idea()
        if not idea:
            reply(channel, "目前沒有任何投稿喔！")
        else:
            reply(channel, f"抽到：{idea['idea_id']}\n輸入 IDEA 編號即可查看詳細內容")
        return

    # 平台查詢
    if is_platform(text):
        ideas = get_ideas_by_platform(text)
        if not ideas:
            reply(channel, f"沒有找到與 {text} 相關的 idea")
        else:
            ids = "\n".join([i["idea_id"] for i in ideas])
            reply(channel, f"{text} 相關的 idea：\n{ids}\n輸入 IDEA 編號即可查看詳細內容")
        return

    # 關鍵字查詢
    if is_keyword(text):
        ideas = get_ideas_by_keyword(text)
        if not ideas:
            reply(channel, f"沒有找到與 {text} 相關的 idea")
        else:
            ids = "\n".join([i["idea_id"] for i in ideas])
            reply(channel, f"{text} 相關的 idea：\n{ids}\n輸入 IDEA 編號即可查看詳細內容")
        return

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
                timeout=10,
            )
        return

    # fallback
    reply(
        channel,
        "你可以輸入：\n"
        "- 抽\n"
        "- 平台名稱（Instagram / Facebook / Threads / Reels / Storys / Big idea）\n"
        "- 關鍵字（星座 / 節慶 / 借勢 / 諧音 / MBTI / 測驗網 / 短期案 / 殺手鐧 / 貼文大賞 / 遺珠 / 其它）\n"
        "- IDEA 編號（例如：IDEA-000001）"
    )


# -----------------------------
# /submit-idea：Slash Command 開啟投稿 Modal（含正確 ACK）
# -----------------------------
@app.route("/submit-idea", methods=["POST"])
def open_idea_form():
    # 1) 驗證 Slack 簽名
    if not verify_slack_request(request):
        return "Invalid request", 403

    # 2) 防 Slack retry 重送（避免同一個 slash command 開多次 modal）
    if request.headers.get("X-Slack-Retry-Num"):
        return "", 200

    payload = request.form
    trigger_id = payload.get("trigger_id")

    # Slash command 一定要回 200（ephemeral），避免 operation_timeout
    if not trigger_id:
        return jsonify({
            "response_type": "ephemeral",
            "text": "找不到 trigger_id，請確認 Slash Command 設定正確，或重新再試一次。"
        }), 200

    modal = idea_form_modal()

    # 3) 呼叫 Slack API 開啟 modal
    resp = requests.post(
        "https://slack.com/api/views.open",
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"trigger_id": trigger_id, "view": modal},
        timeout=10,
    )

    # 4) 仍需回 200 ACK，並給使用者 feedback
    try:
        data = resp.json()
    except Exception:
        data = {"ok": False, "error": "invalid_json"}

    if not data.get("ok"):
        return jsonify({
            "response_type": "ephemeral",
            "text": (
                "我有收到指令，但開啟投稿表單失敗："
                f"`{data.get('error', 'unknown_error')}`\n"
                "請確認 Bot 權限（scopes）與 Interactivity 設定。"
            )
        }), 200

    return jsonify({
        "response_type": "ephemeral",
        "text": "已為你開啟投稿表單 ✅（若沒跳出視窗，請確認 Slack 沒有擋彈窗）"
    }), 200


# -----------------------------
# /slack/interactions：接收 modal submission（投稿寫 DB）
# -----------------------------
@app.route("/slack/interactions", methods=["POST"])
def slack_interactions():
    if not verify_slack_request(request):
        return "Invalid request", 403

    raw = request.form.get("payload") or request.get_data(as_text=True)
    payload = json.loads(raw)

    if payload.get("type") == "view_submission":
        values = payload["view"]["state"]["values"]

        platform_block = values.get("platform", {})
        platform_input = platform_block.get("platform_select", {})
        platforms = [opt["value"] for opt in platform_input.get("selected_options", [])]

        keyword_block = values.get("keywords", {})
        keyword_input = keyword_block.get("keyword_select", {})
        keywords = [opt["value"] for opt in keyword_input.get("selected_options", [])]

        other_block = values.get("keyword_other", {})
        other_input = other_block.get("keyword_other_input", {})
        other_keyword = other_input.get("value") or ""
        if other_keyword:
            keywords.append(other_keyword)

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
            if v.startswith("//"):
                v = "https:" + v

            links.setdefault(k.strip(), []).append(v)

        extra_block = values.get("extra_info", {})
        extra_input = extra_block.get("extra_info_input", {})
        extra_info = extra_input.get("value") or ""

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
# Events API：支援 DM + @bot（共用 handle_query）
# -----------------------------
@app.route("/events", methods=["POST"])
def slack_events():
    if not verify_slack_request(request):
        return "Invalid request", 403

    data = request.get_json(silent=True) or {}

    # Slack URL 驗證
    if "challenge" in data:
        return data["challenge"], 200

    event = data.get("event", {})
    event_type = event.get("type")
    channel_type = event.get("channel_type")
    text = event.get("text", "") or ""
    channel = event.get("channel")
    user = event.get("user")

    # 避免 bot 自己觸發自己（防無限循環）
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return "", 200
    if BOT_USER_ID and user == BOT_USER_ID:
        return "", 200

    # 1) DM 模式（message.im）
    if event_type == "message" and channel_type == "im":
        text = text.strip()

        # 避免 hi / hello 造成亂觸發（保留你原本邏輯）
        if text.lower() in ["hi", "hello", "嗨", "哈囉"]:
            return "", 200

        handle_query(text, channel)
        return "", 200

    # 2) @bot 模式（app_mention）
    if event_type == "app_mention":
        if BOT_USER_ID:
            # Slack 常見格式 "<@Uxxx>"；有些情況會變成 "&lt;@Uxxx&gt;"
            text = text.replace(f"<@{BOT_USER_ID}>", "")
            text = text.replace(f"&lt;@{BOT_USER_ID}&gt;", "")
            text = text.replace("\n", " ").replace("\r", " ").strip()

        handle_query(text, channel)
        return "", 200

    return "", 200


# -----------------------------
# 啟動 Flask（Railway 必須）
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)