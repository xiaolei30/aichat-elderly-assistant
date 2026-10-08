"""天气获取：联网定位「当前位置」（IP 自动识别），再经 open-meteo 获取天气；失败回退默认城市估算。"""
import time

import httpx

import config

# IP 定位（免费、无需密钥，HTTP 端点 + lang=zh-CN 返回中文城市名）
_IP_API = "http://ip-api.com/json/?lang=zh-CN&fields=status,message,country,city,lat,lon"
_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# WMO weathercode -> 中文天气
_WMO_CN = {
    0: "晴", 1: "晴", 2: "多云", 3: "阴",
    45: "雾", 48: "雾",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "阵雪",
    95: "雷阵雨", 96: "雷阵雨", 99: "雷阵雨",
}

_weather_cache = {"time": 0.0, "data": None}
_location_cache = {"time": 0.0, "data": None}
_WEATHER_TTL = 10 * 60   # 天气缓存 10 分钟
_LOCATION_TTL = 60 * 60  # 位置缓存 1 小时（IP 基本不变）


def _advice_for(condition: str, temp: int, high: int) -> str:
    """按天气生成一句面向老人的健康建议。"""
    if any(k in condition for k in ("雨", "雪", "雷")):
        return "今天有雨，路面湿滑，尽量少出门，出门记得带伞。"
    if temp >= 32 or high >= 34:
        return "今天天气炎热，注意防暑降温，多喝水，避免中午外出。"
    if high <= 12:
        return "今天天气偏凉，注意保暖，早晚多穿一件衣服。"
    return "今天天气不错，适合出门散散步，记得防晒、多喝水。"


async def _get_location() -> dict:
    """联网定位当前位置（IP），失败回退默认城市。返回 {city, lat, lon}。"""
    if _location_cache["data"] and time.time() - _location_cache["time"] < _LOCATION_TTL:
        return _location_cache["data"]

    loc = {"city": config.CITY, "lat": config.CITY_LAT, "lon": config.CITY_LON}
    try:
        # trust_env=False：绕过本机代理直连，避免代理出口（如境外节点）导致定位错误
        async with httpx.AsyncClient(timeout=6.0, trust_env=False) as client:
            data = (await client.get(_IP_API)).json()
        if data.get("status") == "success" and data.get("lat") and data.get("lon"):
            loc = {
                "city": data.get("city") or config.CITY,
                "lat": float(data["lat"]),
                "lon": float(data["lon"]),
            }
    except Exception:
        pass

    _location_cache["data"] = loc
    _location_cache["time"] = time.time()
    return loc


def _fallback_weather(city: str) -> dict:
    """兜底：按电脑系统月份估算天气，保证演示始终有数据。"""
    month = time.localtime().tm_mon
    if month in (12, 1, 2):
        condition, high, low = "多云", 20, 11
    elif month in (6, 7, 8):
        condition, high, low = "晴", 33, 26
    elif month in (3, 4, 5):
        condition, high, low = "小雨", 27, 20
    else:
        condition, high, low = "晴", 29, 21
    temp = (high + low) // 2
    return {
        "city": city,
        "condition": condition,
        "temp": temp,
        "temp_high": high,
        "temp_low": low,
        "wind": "微风",
        "advice": _advice_for(condition, temp, high),
        "source": "fallback",
        "updated_at": time.strftime("%H:%M"),
    }


async def get_weather() -> dict:
    """返回当前位置当日天气（联网），带缓存；失败回退本地估算。"""
    if _weather_cache["data"] and time.time() - _weather_cache["time"] < _WEATHER_TTL:
        return _weather_cache["data"]

    loc = await _get_location()
    try:
        params = {
            "latitude": loc["lat"],
            "longitude": loc["lon"],
            "current_weather": "true",
            "daily": "temperature_2m_max,temperature_2m_min,weathercode",
            "timezone": "Asia/Shanghai",
            "forecast_days": 1,
        }
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            resp = await client.get(_OPEN_METEO, params=params)
            resp.raise_for_status()
            data = resp.json()

        cur = data["current_weather"]
        daily = data["daily"]
        code = cur.get("weathercode", daily["weathercode"][0])
        condition = _WMO_CN.get(code, "多云")
        temp = round(cur["temperature"])
        high = round(daily["temperature_2m_max"][0])
        low = round(daily["temperature_2m_min"][0])
        wind_speed = cur.get("windspeed", 0)

        result = {
            "city": loc["city"],
            "condition": condition,
            "temp": temp,
            "temp_high": high,
            "temp_low": low,
            "wind": f"风速 {wind_speed} km/h",
            "advice": _advice_for(condition, temp, high),
            "source": "open-meteo",
            "updated_at": time.strftime("%H:%M"),
        }
    except Exception:
        result = _fallback_weather(loc["city"])

    _weather_cache["data"] = result
    _weather_cache["time"] = time.time()
    return result
