from typing import Any, Callable, Dict, Set
import asyncio


class CommunicationBus:
    def __init__(self):
        self.subscription_repository: Dict[str, Set[Callable]] = {}
        self._lock = asyncio.Lock()

    async def subscribe_listener(self, topic_name: str, listener: Callable):
        async with self._lock:
            self.subscription_repository.setdefault(topic_name, set()).add(listener)

    async def publish(self, topic_name: str, value: Any):
        listeners = self.subscription_repository.get(topic_name, set())
        if not listeners:
            return

        async_calls = []
        for listener in listeners:
            if asyncio.iscoroutinefunction(listener):
                async_calls.append(listener(value))
            else:
                listener(value)

        if async_calls:
            await asyncio.gather(*async_calls)
