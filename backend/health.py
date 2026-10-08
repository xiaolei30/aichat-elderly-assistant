"""健康数据：模拟生成血压/心率/血糖（演示用，可替换为真实设备上报）。"""
import random
import time

_cache = {"time": 0.0, "data": None}
_TTL = 8  # 缓存 8 秒，与前端轮询节奏匹配

# 各异常项的老人注意事项
HEALTH_ADVICE = {
    "bp": "血压偏高，注意少吃盐、清淡饮食，按时吃降压药，保持心情平静。",
    "hr": "心率异常，注意多休息，避免剧烈活动，如持续不适请联系家人或就医。",
    "glu": "血糖偏高，注意少吃甜食和主食，适量散步运动，按时服药。",
}


def _gen() -> dict:
    bp = {"sys": random.randint(112, 135), "dia": random.randint(70, 84)}
    hr = random.randint(64, 88)
    glu = round(random.uniform(4.4, 6.4), 1)

    bp_ok = bp["sys"] < 140 and bp["dia"] < 90
    hr_ok = 60 <= hr <= 100
    glu_ok = 3.9 <= glu <= 6.1

    problems = []
    if not bp_ok:
        problems.append(HEALTH_ADVICE["bp"])
    if not hr_ok:
        problems.append(HEALTH_ADVICE["hr"])
    if not glu_ok:
        problems.append(HEALTH_ADVICE["glu"])

    return {
        "bp": {**bp, "status": "normal" if bp_ok else "warn"},
        "hr": {"value": hr, "status": "normal" if hr_ok else "warn"},
        "glu": {"value": glu, "status": "normal" if glu_ok else "warn"},
        "abnormal": bool(problems),
        "advice": " ".join(problems),
        "updated_at": time.strftime("%H:%M:%S"),
    }


def get_health() -> dict:
    """返回当前健康数据，带缓存，避免每次请求都变化。"""
    if _cache["data"] and time.time() - _cache["time"] < _TTL:
        return _cache["data"]
    _cache["data"] = _gen()
    _cache["time"] = time.time()
    return _cache["data"]
