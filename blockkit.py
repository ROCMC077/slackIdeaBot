import json

# -----------------------------
# 投稿表單（Modal）
# -----------------------------
def idea_form_modal():
    return {
        "type": "modal",
        "callback_id": "submit_idea_form",
        "title": {"type": "plain_text", "text": "投稿 Idea"},
        "submit": {"type": "plain_text", "text": "提交"},
        "close": {"type": "plain_text", "text": "取消"},
        "blocks": [
            {
                "type": "input",
                "block_id": "platform",
                "element": {
                    "type": "multi_static_select",
                    "placeholder": {"type": "plain_text", "text": "選擇平台"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Instagram"}, "value": "Instagram"},
                        {"text": {"type": "plain_text", "text": "Facebook"}, "value": "Facebook"},
                        {"text": {"type": "plain_text", "text": "Threads"}, "value": "Threads"},
                        {"text": {"type": "plain_text", "text": "Reels"}, "value": "Reels"},
                        {"text": {"type": "plain_text", "text": "Storys"}, "value": "Storys"},
                        {"text": {"type": "plain_text", "text": "Big idea"}, "value": "Big idea"}
                    ],
                    "action_id": "platform_select"
                },
                "label": {"type": "plain_text", "text": "平台（多選）"}
            },
            {
                "type": "input",
                "block_id": "keywords",
                "element": {
                    "type": "multi_static_select",
                    "placeholder": {"type": "plain_text", "text": "選擇關鍵字"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "星座"}, "value": "星座"},
                        {"text": {"type": "plain_text", "text": "節慶"}, "value": "節慶"},
                        {"text": {"type": "plain_text", "text": "借勢"}, "value": "借勢"},
                        {"text": {"type": "plain_text", "text": "諧音"}, "value": "諧音"},
                        {"text": {"type": "plain_text", "text": "MBTI"}, "value": "MBTI"},
                        {"text": {"type": "plain_text", "text": "測驗網"}, "value": "測驗網"},
                        {"text": {"type": "plain_text", "text": "短期案"}, "value": "短期案"},
                        {"text": {"type": "plain_text", "text": "殺手鐧"}, "value": "殺手鐧"},
                        {"text": {"type": "plain_text", "text": "貼文大賞"}, "value": "貼文大賞"},
                        {"text": {"type": "plain_text", "text": "遺珠"}, "value": "遺珠"},
                        {"text": {"type": "plain_text", "text": "其它"}, "value": "其它"}
                    ],
                    "action_id": "keyword_select"
                },
                "label": {"type": "plain_text", "text": "關鍵字（多選）"}
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "keyword_other",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "keyword_other_input"
                },
                "label": {"type": "plain_text", "text": "若選其它，請填寫關鍵字"}
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "links",
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "links_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "格式：\n規劃：https://...\n貼文：https://...\n其它：https://..."
                    }
                },
                "label": {"type": "plain_text", "text": "連結（可多筆）"}
            },
            {
                "type": "input",
                "optional": True,
                "block_id": "extra_info",
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "extra_info_input"
                },
                "label": {"type": "plain_text", "text": "補充資訊"}
            }
        ]
    }


# -----------------------------
# Idea 詳細內容卡片（Block Kit）
# -----------------------------
def idea_detail_block(idea):
    platforms = "、".join(idea.get("platforms", []))
    keywords = "、".join(idea.get("keywords", []))

    # -----------------------------
    # 🔥 安全處理 links（永不 crash）
    # -----------------------------
    raw_links = idea.get("links")

    # 1. 如果 links 是字串 → 嘗試轉成 JSON
    if isinstance(raw_links, str):
        try:
            links = json.loads(raw_links)
        except:
            links = {}
    else:
        links = raw_links

    # 2. 如果不是 dict → 強制變成 {}
    if not isinstance(links, dict):
        links = {}

    # -----------------------------
    # 🔥 格式化連結（保留你原本的呈現方式）
    # -----------------------------
    link_lines = []
    for category, urls in links.items():

        # urls 可能是字串 → 包成 list
        if isinstance(urls, str):
            urls = [urls]

        for url in urls:
            link_lines.append(f"- *{category}*：<{url}>")

    links_text = "\n".join(link_lines) if link_lines else "（無）"

    extra_info = idea.get("extra_info") or "（無）"

    # -----------------------------
    # 🔥 完全保留你原本的 Block Kit
    # -----------------------------
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": idea["idea_id"]}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*平台：*\n{platforms}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*關鍵字：*\n{keywords}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*連結：*\n{links_text}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*補充資訊：*\n{extra_info}"
            }
        }
    ]