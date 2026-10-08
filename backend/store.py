"""JSON 文件存储：用于持久化用药提醒（线程安全）。"""
import json
import os
import threading
import time
import uuid


class JsonStore:
    """一个基于 JSON 文件的极简列表存储。"""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not os.path.exists(self.path):
            with self._lock:
                self._write([])

    def _read(self) -> list:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, data: list) -> None:
        # 先写临时文件再原子替换，避免写一半损坏数据
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list(self, user_id: str | None = None) -> list:
        with self._lock:
            data = self._read()
        if user_id:
            data = [r for r in data if r.get("user_id") == user_id]
        return data

    def add(self, item: dict) -> dict:
        with self._lock:
            data = self._read()
            item = dict(item)
            item["id"] = item.get("id") or uuid.uuid4().hex[:12]
            item["created_at"] = item.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
            data.append(item)
            self._write(data)
        return item

    def delete(self, reminder_id: str) -> bool:
        with self._lock:
            data = self._read()
            new_data = [r for r in data if r.get("id") != reminder_id]
            removed = len(new_data) != len(data)
            if removed:
                self._write(new_data)
        return removed

    def replace(self, items: list) -> list:
        """整体覆盖列表（用于「每日用药计划」整体保存），为每条补齐 id/创建时间。"""
        with self._lock:
            data = []
            for item in items:
                item = dict(item)
                item["id"] = item.get("id") or uuid.uuid4().hex[:12]
                item["created_at"] = item.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
                data.append(item)
            self._write(data)
        return data

    def replace_for_user(self, user_id: str, items: list) -> list:
        """仅替换该用户的条目，其他用户的数据不受影响（用于账号隔离）。"""
        with self._lock:
            data = [r for r in self._read() if r.get("user_id") != user_id]
            for item in items:
                item = dict(item)
                item["user_id"] = user_id
                item["id"] = item.get("id") or uuid.uuid4().hex[:12]
                item["created_at"] = item.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")
                data.append(item)
            self._write(data)
        return data
