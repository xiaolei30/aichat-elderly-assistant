"""银龄守望后端服务：语音助手对话 + 天气/健康/联系人/用药计划 + 呼救检测。"""
import logging
import time
import memoir
from pathlib import Path
from typing import Optional
from fastapi import Request

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
import health
import intents
import llm
import weather
from store import JsonStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("yinlingshouwang")

app = FastAPI(title="银龄守望后端", version="2.0.0")

# 前端可能以 file:// 打开或独立部署，放开跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 前端单页（index.html）路径，由后端直接托管，浏览器访问 http://localhost:8000 即可
FRONTEND_INDEX = Path(__file__).resolve().parent.parent / "index.html"


@app.get("/")
def serve_index():
    """托管前端页面，使语音识别处于 localhost 安全上下文，避免 file:// 下不可用。"""
    return FileResponse(FRONTEND_INDEX)


store = JsonStore(config.REMINDERS_FILE)
contacts = JsonStore(config.CONTACTS_FILE)
medplan = JsonStore(config.MEDPLAN_FILE)

# 简单的会话记忆（内存，进程重启即清空）
_history: dict[str, list[dict]] = {}
_HISTORY_MAX = 12

# 无登录：统一使用一个默认用户，数据持久化到本地文件，下次启动自动恢复
DEFAULT_USER = "elderly_001"


class ChatRequest(BaseModel):
    message: str
    user_id: str = "elderly_001"


class ReminderCreate(BaseModel):
    user_id: str = "elderly_001"
    drug: Optional[str] = None
    hour: Optional[int] = None
    minute: int = 0
    time_label: Optional[str] = None
    repeat: str = ""


class ContactCreate(BaseModel):
    name: str
    phone: str


class MedPlanItem(BaseModel):
    drug: str
    time: str  # "HH:MM"
    dose: str = ""


class MedPlanCreate(BaseModel):
    plan: list[MedPlanItem]


def _now_hm() -> str:
    return time.strftime("%H:%M")


def _reminder_reply(rem: dict) -> str:
    """根据解析出的提醒信息，生成确认或追问话术。"""
    drug = rem.get("drug")
    time_label = rem.get("time_label")
    repeat = rem.get("repeat") or ""

    if not time_label and not drug:
        return "好的，我来帮您设置用药提醒。请问您吃什么药、几点吃呢？"
    if not time_label:
        return f"好的，{drug}。请问您每天几点吃呢？"
    if not drug:
        return f"好的，我记住了，{repeat}{time_label} 提醒您。请问是什么药呢？"
    return f"好的，我帮您记下来了：{repeat}{time_label} 吃{drug}。到时间我会提醒您的。"


async def _chat_with_llm(text: str, user_id: str) -> tuple[str, str]:
    """常规对话：优先 DeepSeek，失败则本地兜底。"""
    history = _history.setdefault(user_id, [])
    history.append({"role": "user", "content": text})
    if len(history) > _HISTORY_MAX:
        history = history[-_HISTORY_MAX:]

    try:
        reply = await llm.chat_completion(history)
        source = "deepseek"
    except Exception as exc:
        logger.warning("DeepSeek 调用失败，回退本地回复: %s", exc)
        reply = llm.local_reply(text)
        source = "local"

    history.append({"role": "assistant", "content": reply})
    if len(history) > _HISTORY_MAX:
        history = history[-_HISTORY_MAX:]
    _history[user_id] = history
    return reply, source


# ===== 天气 / 健康 / 今日播报 =====

@app.get("/api/weather")
async def get_weather():
    return await weather.get_weather()


@app.get("/api/health-data")
def get_health_data():
    return health.get_health()


@app.get("/api/report")
async def report():
    """今日播报：天气 + 健康建议 + 用药情况 + 身体状况，返回可直接朗读的文本。"""
    w = await weather.get_weather()
    h = health.get_health()
    plan = medplan.list(DEFAULT_USER)
    now = _now_hm()

    total = len(plan)
    done = sum(1 for m in plan if m.get("time", "") < now)
    future = sorted((m for m in plan if m.get("time", "") >= now), key=lambda m: m["time"])
    nxt = future[0]["time"] if future else None

    text = f"今日播报。{w['city']}今天{w['condition']}，{w['temp_low']}到{w['temp_high']}度。{w['advice']}"

    if total:
        med = f"今日用药{total}次，已完成{done}次"
        if nxt:
            med += f"，下次{nxt}"
        text += med + "。"
    else:
        text += "今天还没有设置用药计划。"

    if h["abnormal"]:
        text += "身体状况需要留意。" + h["advice"]
    else:
        text += "身体状况良好，请继续保持。"

    return {
        "text": text,
        "weather": w,
        "health": h,
        "medication": {"total": total, "done": done, "next": nxt},
    }


# ===== 联系人（子女号码） =====

@app.get("/api/contacts")
def list_contacts():
    return {"contacts": contacts.list(DEFAULT_USER)}


@app.post("/api/contacts")
def create_contact(req: ContactCreate):
    item = contacts.add({"user_id": DEFAULT_USER, "name": req.name.strip(), "phone": req.phone.strip()})
    return {"contact": item}


@app.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: str):
    if not any(c.get("id") == contact_id for c in contacts.list(DEFAULT_USER)):
        raise HTTPException(status_code=404, detail="联系人不存在")
    contacts.delete(contact_id)
    return {"ok": True}


# ===== 每日用药计划 =====

@app.get("/api/medplan")
def get_medplan():
    plan = medplan.list(DEFAULT_USER)
    now = _now_hm()
    total = len(plan)
    done = sum(1 for m in plan if m.get("time", "") < now)
    future = sorted((m for m in plan if m.get("time", "") >= now), key=lambda m: m["time"])
    return {"plan": plan, "total": total, "done": done, "next": future[0]["time"] if future else None}


@app.post("/api/medplan")
def set_medplan(req: MedPlanCreate):
    items = [{"drug": m.drug.strip(), "time": m.time, "dose": m.dose.strip() or "1次"} for m in req.plan]
    saved = medplan.replace_for_user(DEFAULT_USER, items)
    return {"plan": saved}


@app.get("/api/medplan/due")
def medplan_due():
    """返回当前时刻到点的用药，供前端轮询做「到点提醒」。"""
    now = _now_hm()
    due = [m for m in medplan.list(DEFAULT_USER) if m.get("time") == now]
    return {"due": due, "now": now}


# ===== 服务状态 =====

@app.get("/api/health")
def health_check():
    return {"status": "ok", "llm_configured": bool(config.DEEPSEEK_API_KEY)}


# ===== 对话 =====

@app.post("/api/chat")
async def chat(req: ChatRequest):
    text = (req.message or "").strip()
    user_id = DEFAULT_USER
    if not text:
        return {"reply": "我没听清，请您再说一遍。", "risk_alert": False, "intent": "empty"}

    # 1) 紧急呼救检测（优先级最高）
    if intents.detect_risk(text):
        reply = "您别急，我马上帮您联系家人！请您先尽量保持平静，好吗？"
        return {"reply": reply, "risk_alert": True, "intent": "risk"}

    # 2) 打电话给家人
    relation = intents.detect_call(text)
    if relation:
        matched = next((c for c in contacts.list(DEFAULT_USER) if c.get("name") == relation), None)
        if matched:
            reply = f"好的，我帮您拨打{relation}的电话。"
            return {"reply": reply, "risk_alert": False, "intent": "call",
                    "call": {"name": relation, "phone": matched["phone"]}}
        reply = "我还没有存这个家人的号码，可以让子女在设置里帮您添加。"
        return {"reply": reply, "risk_alert": False, "intent": "call", "call": None}

    # 3) 用药提醒
    if intents.is_reminder(text):
        reminder = intents.parse_reminder(text) or {}
        reminder.update({"user_id": user_id, "raw": text})
        saved = store.add(reminder)
        return {
            "reply": _reminder_reply(saved),
            "risk_alert": False,
            "intent": "reminder",
            "reminder": saved,
        }

    # 4) 常规对话
    reply, source = await _chat_with_llm(text, user_id)
    return {"reply": reply, "risk_alert": False, "intent": "chat", "source": source}


@app.get("/api/reminders")
def list_reminders():
    return {"reminders": store.list(DEFAULT_USER)}


@app.post("/api/reminders")
def create_reminder(req: ReminderCreate):
    item = req.model_dump()
    item["user_id"] = DEFAULT_USER
    saved = store.add(item)
    return {"reminder": saved}


@app.delete("/api/reminders/{reminder_id}")
def delete_reminder(reminder_id: str):
    if not any(r.get("id") == reminder_id for r in store.list(DEFAULT_USER)):
        raise HTTPException(status_code=404, detail="提醒不存在")
    store.delete(reminder_id)
    return {"ok": True}

# ===== 银龄回忆相册 =====

@app.post("/api/memoir/organize")
async def api_organize_memory(req: dict):
    """口述成册：把老人说的话整理成回忆录。"""
    text = req.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    result = await memoir.organize_memory(text)
    return result


@app.post("/api/memoir/follow-up")
async def api_follow_up(req: dict):
    """温和反问：AI引导老人继续说。"""
    text = req.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    question = await memoir.gentle_follow_up(text)
    return {"question": question}


@app.post("/api/memoir/save")
def api_save_memory(req: memoir.MemoirCreate):
    """保存一条回忆录。"""
    saved = memoir.save_memory(req)
    return {"memory": saved}


@app.get("/api/memoir/timeline")
def api_get_timeline():
    """子女端时间线：获取所有回忆。"""
    items = memoir.get_timeline(DEFAULT_USER)
    return {"memoirs": items, "total": len(items)}


@app.delete("/api/memoir/{memory_id}")
def api_delete_memory(memory_id: str):
    """删除一条回忆。"""
    ok = memoir.delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="回忆不存在")
    return {"ok": True}

# AI自动识别年代
@app.post("/api/memoir/guess-year")
async def api_guess_year(req: dict):
    text = req.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    year = await memoir.guess_year(text)
    return {"year": year}


# 上传音频
@app.post("/api/memoir/upload-audio")
async def api_upload_audio(request: Request):
    form = await request.form()
    audio = form.get("audio")
    if not audio:
        raise HTTPException(status_code=400, detail="没有音频文件")
    content = await audio.read()
    filename = memoir.save_audio(audio.filename, content)
    return {"filename": filename}


# 下载音频
@app.get("/api/memoir/audio/{filename}")
def api_get_audio(filename: str):
    from pathlib import Path
    from fastapi.responses import FileResponse
    filepath = Path(__file__).resolve().parent / "memoir_audio" / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="音频不存在")
    return FileResponse(filepath, media_type="audio/wav")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
