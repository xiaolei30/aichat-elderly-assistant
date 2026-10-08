"""意图识别：紧急呼救检测 + 用药提醒解析（无需模型即可运行）。"""
import re

# 命中即触发风险告警的关键词
RISK_KEYWORDS = [
    "救命", "救我", "快来人", "不行了", "要死了",
    "摔倒了", "摔了", "起不来", "站不起来",
    "喘不过气", "呼吸困难", "胸口痛", "心脏不舒服", "心绞痛",
    "叫救护车", "打120", "急救",
]

# 用药提醒触发词
REMINDER_KEYWORDS = [
    "提醒", "吃药", "服药", "用药", "该吃药", "闹钟", "记下来", "帮我记",
]

_CN_NUM = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

# 这些是泛指，不算具体药名
_GENERIC_DRUG = {"药", "用药", "服药", "吃药", "片", "丸", "胶囊", "颗粒"}

# 常见食物/非药名，避免把「吃饭」「吃水果」误判成用药提醒
_NON_DRUG = _GENERIC_DRUG | {
    "饭", "早饭", "午饭", "晚饭", "早餐", "午餐", "晚餐", "夜宵",
    "水果", "苹果", "香蕉", "橘子", "鸡蛋", "米饭", "面条", "饺子",
}


def _cn_to_int(s: str):
    """把中文数字（一到九十九）转成整数，无法解析返回 None。"""
    if not s:
        return None
    if s == "十":
        return 10
    if "十" in s:
        left, _, right = s.partition("十")
        tens = _CN_NUM.get(left, 1) if left else 1
        ones = _CN_NUM.get(right, 0) if right else 0
        return tens * 10 + ones
    return _CN_NUM.get(s)


def _extract_time(text: str):
    """返回 (hour, minute)，解析失败返回 (None, None)。"""
    # 24 小时制 "8:30" / "18:00"
    m = re.search(r"(\d{1,2})\s*[:：]\s*(\d{1,2})", text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    # 阿拉伯数字点 "8点" / "8点半"
    m = re.search(r"(\d{1,2})\s*点\s*半?", text)
    if m:
        hour = int(m.group(1))
        if 0 <= hour <= 23:
            return hour, 30 if "半" in m.group(0) else 0
    # 中文数字点 "八点" / "八点半"
    m = re.search(r"([一二三四五六七八九十两零]{1,3})\s*点\s*半?", text)
    if m:
        hour = _cn_to_int(m.group(1))
        if hour is not None and 0 <= hour <= 23:
            return hour, 30 if "半" in m.group(0) else 0
    return None, None


def _apply_period(text: str, hour):
    """根据下午/晚上等修饰词调整小时数。"""
    if hour is None:
        return hour
    if any(w in text for w in ("下午", "傍晚", "晚上", "夜里")):
        if hour < 12:
            return hour + 12
    if "中午" in text and hour < 11:
        return hour + 12
    return hour


def _extract_drug(text: str):
    """尝试从文本中抽取药品名，抽不到返回 None。"""
    # 「吃/喝/服 + 药名」模式最可靠
    m = re.search(r"[吃喝服]([一-龥A-Za-z0-9]{1,10})", text)
    if m:
        drug = re.sub(r"^(用|一粒|一颗|一片|半片|两粒|两片|的)", "", m.group(1))
        drug = drug.rstrip("的了吧呢吗啊哦")
        if drug and drug not in _NON_DRUG:
            return drug
    return None


def detect_risk(text: str) -> bool:
    return any(kw in text for kw in RISK_KEYWORDS)


def is_reminder(text: str) -> bool:
    if any(kw in text for kw in REMINDER_KEYWORDS):
        return True
    # 自然说法：出现「吃/喝/服 + 具体药名」也算提醒
    if re.search(r"[吃喝服]", text) and _extract_drug(text) is not None:
        return True
    return False


def parse_reminder(text: str) -> dict | None:
    """解析用药提醒，返回结构化字段；非提醒意图返回 None。"""
    if not is_reminder(text):
        return None

    hour, minute = _extract_time(text)
    hour = _apply_period(text, hour)
    drug = _extract_drug(text)
    repeat = "每天" if ("每天" in text or "每日" in text or "天天" in text) else ""

    time_label = f"{hour:02d}:{minute:02d}" if hour is not None else None

    return {
        "drug": drug,
        "hour": hour,
        "minute": minute,
        "time_label": time_label,
        "repeat": repeat,
    }


# 老人常用称呼，用于「打电话给XX」
CALL_RELATIONS = [
    "女儿", "儿子", "闺女", "孙子", "孙女", "外孙", "外孙女",
    "老伴", "爱人", "老头", "老婆", "家人", "孩子", "儿媳", "女婿",
    "姐姐", "妹妹", "哥哥", "弟弟", "侄子", "侄女",
]


def detect_call(text: str):
    """识别「打电话/呼叫/拨号 + 称呼」，返回称呼；纯打电话返回「家人」；否则 None。"""
    if not any(k in text for k in ("打电话", "呼叫", "拨号")):
        return None
    for rel in CALL_RELATIONS:
        if rel in text:
            return rel
    return "家人"
