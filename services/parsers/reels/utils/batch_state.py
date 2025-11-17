from __future__ import annotations

import json
import re
from pathlib import Path
from threading import Lock
from typing import Iterable, Set


class BatchProgressStore:
    """Файловое хранилище прогресса batch-парсинга Instagram."""

    def __init__(self, base_dir: str):
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _file_path(self, batch_id: str) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", batch_id)
        return self._base_dir / f"{safe_name}.json"

    def load(self, batch_id: str) -> Set[int]:
        path = self._file_path(batch_id)
        if not path.exists():
            return set()
        try:
            data = json.loads(path.read_text())
        except Exception:
            return set()
        processed = data.get("processed") if isinstance(data, dict) else None
        if not isinstance(processed, list):
            return set()
        result: Set[int] = set()
        for item in processed:
            try:
                result.add(int(item))
            except (TypeError, ValueError):
                continue
        return result

    def _dump(self, batch_id: str, processed: Iterable[int]) -> None:
        path = self._file_path(batch_id)
        payload = {"processed": sorted(set(processed))}
        path.write_text(json.dumps(payload))

    def mark_processed(self, batch_id: str, channel_id: int) -> None:
        with self._lock:
            processed = self.load(batch_id)
            if channel_id in processed:
                return
            processed.add(channel_id)
            self._dump(batch_id, processed)

    def clear(self, batch_id: str) -> None:
        path = self._file_path(batch_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return
