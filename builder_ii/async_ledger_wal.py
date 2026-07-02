import asyncio
import json
import mmap
from pathlib import Path
from typing import Any


class AsyncLedgerWAL:
    """Memory-mapped Write-Ahead Log for high-performance, non-blocking ledger writes."""

    def __init__(self, path: Path, max_size: int = 10 * 1024 * 1024):
        self.path = path
        self.max_size = max_size
        self._lock = asyncio.Lock()

        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch()
            with self.path.open("r+b") as f:
                f.truncate(self.max_size)
            self.offset = 0
        else:
            with self.path.open("r+b") as f:
                content = f.read()
                # Find length of file excluding trailing null bytes
                self.offset = len(content.rstrip(b"\x00"))
                if self.offset >= self.max_size:
                    raise RuntimeError(f"WAL {path} capacity exceeded: {self.offset} >= {self.max_size}")

        self._fd = self.path.open("r+b")
        self._mmap = mmap.mmap(self._fd.fileno(), self.max_size, access=mmap.ACCESS_WRITE)

    async def write_record(self, record: dict[str, Any]) -> None:
        payload = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
        async with self._lock:
            if self.offset + len(payload) > self.max_size:
                raise RuntimeError(f"WAL {self.path} is full. Cannot write {len(payload)} bytes.")
            self._mmap.seek(self.offset)
            self._mmap.write(payload)
            self.offset += len(payload)
            # Offload the flush to an executor thread so it doesn't block the event loop
            await asyncio.to_thread(self._mmap.flush)

    def write_record_sync(self, record: dict[str, Any]) -> None:
        """Public synchronous append — use from non-async callers."""
        payload = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
        if self.offset + len(payload) > self.max_size:
            raise RuntimeError(f"WAL {self.path} is full. Cannot write {len(payload)} bytes.")
        self._mmap.seek(self.offset)
        self._mmap.write(payload)
        self.offset += len(payload)
        self._mmap.flush()

    def read_records(self) -> list[dict[str, Any]]:
        self._mmap.seek(0)
        data = self._mmap[: self.offset].decode("utf-8", errors="replace")
        records = []
        for line in data.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records

    def close(self) -> None:
        try:
            self._mmap.close()
            self._fd.close()
        except Exception:
            pass
