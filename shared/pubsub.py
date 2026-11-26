import asyncio
import json
from collections import defaultdict
from typing import Any

import asyncpg

from shared.config import settings


def _asyncpg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


class PgPubSubBroker:
    def __init__(self, channel: str = "nyaquiz_events"):
        self.channel = channel
        self._conn: asyncpg.Connection | None = None
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception:
                pass
            self._conn = None
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _listen_loop(self) -> None:
        dsn = _asyncpg_dsn(settings.database_url)
        while not self._stop_event.is_set():
            try:
                self._conn = await asyncpg.connect(dsn)
                await self._conn.add_listener(self.channel, self._on_notify)
                while not self._stop_event.is_set():
                    await asyncio.sleep(5)
                    await self._conn.execute("SELECT 1")
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)
            finally:
                if self._conn is not None:
                    try:
                        await self._conn.close()
                    except Exception:
                        pass
                    self._conn = None

    def _on_notify(self, connection: Any, pid: int, channel: str, payload: str) -> None:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return
        run_id = str(event.get("run_id", ""))
        if not run_id:
            return
        for queue in list(self._subscribers.get(run_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(run_id)
        if subscribers:
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(run_id, None)

    async def publish_local(self, event: dict[str, Any]) -> None:
        run_id = str(event.get("run_id", ""))
        if not run_id:
            return
        for queue in list(self._subscribers.get(run_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass


broker = PgPubSubBroker()
