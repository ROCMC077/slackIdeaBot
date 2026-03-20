# -----------------------------
# 平台列表
# -----------------------------
PLATFORMS = [
    "Instagram",
    "Facebook",
    "Threads",
    "Reels",
    "Storys",
    "Big idea"
]

# -----------------------------
# 關鍵字列表
# -----------------------------
KEYWORDS = [
    "星座",
    "節慶",
    "借勢",
    "諧音",
    "MBTI",
    "測驗網",
    "短期案",
    "殺手鐧",
    "貼文大賞",
    "遺珠",
    "其它"
]


# -----------------------------
# 判斷是否為平台查詢
# -----------------------------
def is_platform(text: str) -> bool:
    return text.strip() in PLATFORMS


# -----------------------------
# 判斷是否為關鍵字查詢
# -----------------------------
def is_keyword(text: str) -> bool:
    return text.strip() in KEYWORDS