from typing import Any, Callable, Dict, Set
import asyncio
import threading

from loguru import logger


class StatefulCommunicationBus:
    def __init__(self):
        self.subscription_repository: Dict[str, Set[Callable]] = {}
        self.last_value_repository: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def subscribe_listener(self, topic_name: str, listener: Callable):
        async with self._lock:
            if topic_name in self.subscription_repository and listener in self.subscription_repository[topic_name]:
                return

            self.subscription_repository.setdefault(topic_name, set()).add(listener)

            if topic_name in self.last_value_repository:
                if asyncio.iscoroutinefunction(listener):
                    await listener(topic_name, self.last_value_repository[topic_name])
                else:
                    listener(topic_name, self.last_value_repository[topic_name])

    async def publish(self, topic_name: str, value: Any):
        async with self._lock:
            self.last_value_repository[topic_name] = value

            listeners = self.subscription_repository.get(topic_name, set())
            if not listeners:
                return

            async_calls = []
            for listener in listeners:
                if asyncio.iscoroutinefunction(listener):
                    async_calls.append(listener(topic_name, value))
                else:
                    listener(topic_name, value)

        if async_calls:
            await asyncio.gather(*async_calls)
