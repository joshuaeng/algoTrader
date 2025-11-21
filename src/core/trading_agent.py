import asyncio
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, TYPE_CHECKING

from loguru import logger

from src.core.communication_bus import CommunicationBus as CommunicationBus
from src.core.data_cache import DataCache
from src.alpaca_wrapper.trading import AlpacaTrading

if TYPE_CHECKING:
    from src.core.trading_hub import TradingHub


def _parse_time_string(time_str: str) -> timedelta:
    """Parses a human-readable time string into a timedelta object."""
    match = re.match(r"(\d+)\s*(ms|milliseconds?|s|seconds?|m|minutes?|h|hours?|d|days?)", time_str, re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid time string format: '{time_str}'")
    value, unit = int(match.group(1)), match.group(2).lower()
    if unit.startswith("ms"):
        return timedelta(milliseconds=value)
    if unit.startswith("s"):
        return timedelta(seconds=value)
    if unit.startswith("m"):
        return timedelta(minutes=value)
    if unit.startswith("h"):
        return timedelta(hours=value)
    if unit.startswith("d"):
        return timedelta(days=value)


class TradingAgent(ABC):
    """Abstract base class for trading agents."""

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        self.config = config
        self.data_cache = data_cache
        self.trading_client: Optional[AlpacaTrading] = None
        self.communication_bus: CommunicationBus = communication_bus
        self.hub: Optional['TradingHub'] = None
        self.validate_config()

    async def initialize(self):
        """Hook for subclasses to perform async initialization."""
        pass

    def set_trading_client(self, trading_client: AlpacaTrading):
        self.trading_client = trading_client

    def set_hub(self, hub: 'TradingHub'):
        """Sets a reference to the trading hub."""
        self.hub = hub

    def validate_config(self):
        """Hook for subclasses to validate their specific configuration."""
        pass


class EventDrivenAgent(TradingAgent):
    """Base class for event-driven trading agents."""

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus,
                 throttle: str = "1s"):
        super().__init__(config, data_cache, communication_bus)
        self._last_execution_time: Optional[datetime] = None
        self._throttle_lock = asyncio.Lock()
        throttle_str = self.config.get('throttle', throttle)
        self.throttle: timedelta = _parse_time_string(throttle_str)
        logger.info(f"[{self.__class__.__name__}] Throttle was set to {self.throttle}.")

    async def start(self, data: Any):
        """Entry point for event-driven execution. Enforces throttling."""
        if self._throttle_lock.locked():
            return

        async with self._throttle_lock:
            now = datetime.utcnow()
            if self._last_execution_time and (now - self._last_execution_time) < self.throttle:
                return

            await self.run(data)
            self._last_execution_time = datetime.utcnow()

    @abstractmethod
    async def run(self, data: Any):
        """The core logic for processing an event."""
        pass


class PeriodicAgent(TradingAgent):
    """Base class for periodic trading agents."""

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus,
                 period: str = "1s"):
        super().__init__(config, data_cache, communication_bus)
        period_str = self.config.get('period', self.config.get('throttle', period))
        self.period: timedelta = _parse_time_string(period_str)
        logger.info(f"[{self.__class__.__name__}] Period was set to {self.period}.")

    @abstractmethod
    async def run(self):
        """The core logic of the periodic task."""
        pass