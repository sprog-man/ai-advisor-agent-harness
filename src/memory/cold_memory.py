"""冷记忆模块 — 原始数据持久化存储"""

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class RawRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    record_type: str = ""  # "conversation" | "tool_call" | "knowledge" | "feedback"
    content: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = "default"


class ColdMemory:
    """冷记忆：原始数据持久化存储（JSON文件）"""

    def __init__(self, storage_dir: Optional[str] = None):
        config = get_config()
        self.storage_dir = storage_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "cold_memory",
        )
        os.makedirs(self.storage_dir, exist_ok=True)
        logger.info("冷记忆存储目录: %s", self.storage_dir)

    def store(self, record: RawRecord) -> str:
        """存储原始记录"""
        file_path = self._get_file_path(record.record_type, record.created_at[:10])
        records = self._load_file(file_path)
        records.append(asdict(record))
        self._save_file(file_path, records)

        logger.debug("冷记忆存储记录: type=%s, id=%s", record.record_type, record.id)
        return record.id

    def retrieve(
        self,
        record_type: Optional[str] = None,
        session_id: Optional[str] = None,
        date: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """检索原始记录"""
        results = []
        files = self._list_files(record_type, date)

        for file_path in files:
            records = self._load_file(file_path)
            for r in records:
                if session_id and r.get("session_id") != session_id:
                    continue
                results.append(r)
                if len(results) >= limit:
                    return results

        return results

    def get_by_id(self, record_id: str) -> Optional[dict]:
        """通过ID获取记录"""
        for file_path in self._list_files():
            records = self._load_file(file_path)
            for r in records:
                if r.get("id") == record_id:
                    return r
        return None

    def count(self, record_type: Optional[str] = None) -> int:
        """统计记录数量"""
        total = 0
        for file_path in self._list_files(record_type):
            records = self._load_file(file_path)
            total += len(records)
        return total

    def _get_file_path(self, record_type: str, date: str) -> str:
        return os.path.join(self.storage_dir, f"{record_type}_{date}.json")

    def _list_files(
        self, record_type: Optional[str] = None, date: Optional[str] = None
    ) -> list[str]:
        files = []
        for f in os.listdir(self.storage_dir):
            if not f.endswith(".json"):
                continue
            if record_type and not f.startswith(record_type):
                continue
            if date and date not in f:
                continue
            files.append(os.path.join(self.storage_dir, f))
        return sorted(files)

    def _load_file(self, file_path: str) -> list[dict]:
        if not os.path.exists(file_path):
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_file(self, file_path: str, records: list[dict]):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
