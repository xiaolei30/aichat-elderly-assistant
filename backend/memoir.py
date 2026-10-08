"""银龄回忆相册：口述成册 + 温和反问 + 子女端时间线 + 音频保存。"""
import time
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from store import JsonStore
import llm
import config

# 存储文件
_memoirs = None
_audio_dir = Path(__file__).resolve().parent / "memoir_audio"


def _store():
    global _memoirs
    if _memoirs is None:
        _memoirs = JsonStore(config.MEMOIRS_FILE)
    return _memoirs


class MemoirCreate(BaseModel):
    user_id: str = "elderly_001"
    title: Optional[str] = None
    content: str = ""
    year: Optional[str] = None      # 年代标签，比如"1965年"
    category: str = "日常"          # 童年/工作/家庭/节日/其他
    audio_filename: Optional[str] = None  # 音频文件名（如果上传了音频）


# ===== 1. 口述成册：AI整理回忆 =====

async def organize_memory(text: str) -> dict:
    prompt = f"""请把下面老人说的一段回忆，整理成一段通顺、温暖的回忆录文字。
要求：
1. 保留老人原来的语气和细节，不要添加虚构内容
2. 句子要短，适合朗读
3. 不要超过100字
4. 开头加一句温暖的引导

老人说的话：{text}"""

    try:
        organized = await llm.chat_completion([{"role": "user", "content": prompt}])
    except Exception:
        organized = text

    return {
        "raw": text,
        "organized": organized,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ===== 2. 温和反问 =====

async def gentle_follow_up(previous_text: str) -> str:
    prompt = f"""老人刚才说了这段话：{previous_text}
请你用非常温和、好奇的语气，问一个问题引导老人继续说下去。
要求：
1. 像家人聊天一样自然
2. 问题要和刚才说的内容相关
3. 不要超过20个字

比如："那时候您多大呀？""后来怎么样了呢？\""""

    try:
        question = await llm.chat_completion([{"role": "user", "content": prompt}])
    except Exception:
        question = "能多跟我说说吗？"

    return question


# ===== 3. AI自动识别年代标签 =====

async def guess_year(text: str) -> str:
    """从回忆内容里自动识别大概年代。"""
    prompt = f"""从下面老人说的回忆里，推断大概是哪一年/哪个年代。
只返回年代，比如"1960年代"、"1970年左右"、"小时候"。
如果完全推断不出来，就返回"未知"。

老人说的话：{text}"""

    try:
        year = await llm.chat_completion([{"role": "user", "content": prompt}])
        return year.strip()
    except Exception:
        return "未知"


# ===== 4. 保存一条回忆录 =====

def save_memory(req: MemoirCreate) -> dict:
    item = {
        "user_id": req.user_id,
        "title": req.title or f"回忆_{time.strftime('%H:%M')}",
        "content": req.content,
        "year": req.year or "未知",
        "category": req.category,
        "audio_filename": req.audio_filename,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    saved = _store().add(item)
    return saved


# ===== 5. 保存音频文件 =====

def save_audio(filename: str, content: bytes) -> str:
    """保存上传的音频文件，返回文件名。"""
    os.makedirs(_audio_dir, exist_ok=True)
    safe_name = f"{int(time.time())}_{filename}"
    filepath = _audio_dir / safe_name
    with open(filepath, "wb") as f:
        f.write(content)
    return safe_name


# ===== 6. 子女端时间线 =====

def get_timeline(user_id: str = "elderly_001") -> list:
    items = _store().list(user_id)
    # 按年代排序，如果没有年代就按创建时间
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


# ===== 7. 删除一条回忆 =====

def delete_memory(memory_id: str) -> bool:
    try:
        _store().delete(memory_id)
        return True
    except Exception:
        return False
