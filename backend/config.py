"""配置加载：优先读环境变量，其次读取 backend/.env 文件。"""
import os
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """极简 .env 加载，避免额外引入 python-dotenv 依赖。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(_BASE_DIR / ".env")

# DeepSeek 相关配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 用药提醒数据存储文件路径
REMINDERS_FILE = os.getenv("REMINDERS_FILE", str(_BASE_DIR / "reminders.json"))

# 天气：联网获取「当前位置」天气（IP 自动定位，失败回退默认城市坐标）
CITY = os.getenv("CITY", "南宁")
CITY_LAT = float(os.getenv("CITY_LAT", "22.82"))
CITY_LON = float(os.getenv("CITY_LON", "108.32"))

# 子女号码 / 每日用药计划存储文件路径
CONTACTS_FILE = os.getenv("CONTACTS_FILE", str(_BASE_DIR / "contacts.json"))
MEDPLAN_FILE = os.getenv("MEDPLAN_FILE", str(_BASE_DIR / "medplan.json"))

#银龄时光回忆相册
MEMOIRS_FILE = os.getenv("MEMOIRS_FILE", str(_BASE_DIR / "memoirs.json"))
