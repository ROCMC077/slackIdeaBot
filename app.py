import os
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from db import init_db, insert_idea

app = Flask(__name__)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")

client = WebClient(token=SLACK_BOT_TOKEN)
verifier = SignatureVerifier(SLACK_SIGNING_SECRET)

# -----------------------------
# 啟動時建立資料表
# -----------------------------
init_db()

# -----------------------------
# Slash Command: /submit-idea
# -----------------------------
@app.route("/submit-idea", methods=["POST"])
def submit_idea():
    trigger_id = request.form.get("trigger_id")

    client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": "idea_modal",
            "title": {"type": "plain_text", "text": "Submit Idea"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "platforms",
                    "label": {"type": "plain_text", "text": "Platforms"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value"
                    }
                },
                {
                    "type": "input",
                    "block_id": "keywords",
                    "label": {"type": "plain_text", "text": "Keywords"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value"
                    }
                },
                {
                    "type": "input",
                    "block_id": "links",
                    "label": {"type": "plain_text", "text": "Links"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value"
                    }
                },
                {
                    "type": "input",
                    "block_id": "extra_info",
                    "label": {"type": "plain_text", "text": "Extra Info"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value"
                    }
                }
            ]
        }
    )

    return "", 200

# -----------------------------
# Modal Submission
# -----------------------------
@app.route("/slack/interactions", methods=["POST"])
def interactions():
    if not verifier.is_valid_request(request.get_data(), request.headers):
        return "invalid signature", 403

    payload = request.form.get("payload")
    if not payload:
        return "", 200

    import json
    data = json.loads(payload)

    if data.get("type") == "view_submission":
        values = data["view"]["state"]["values"]

        platforms = values["platforms"]["value"]["value"].split(",")
        keywords = values["keywords"]["value"]["value"].split(",")
        links = values["links"]["value"]["value"].split(",")
        extra_info = values["extra_info"]["value"]["value"]

        idea_id = insert_idea(platforms, keywords, links, extra_info)

        return jsonify({"response_action": "clear"})

    return "", 200

# -----------------------------
# Flask 啟動
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)