import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from loguru import logger

from src.core.communication_bus import CommunicationBus as CommunicationBus
from src.core.data_cache import DataCache
from src.alpaca_wrapper.trading import AlpacaTrading


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
    """Abstract base class for trading built_in_agents."""

    def __init__(
            self,
            config:
            Dict[str, Any],
            data_cache: DataCache,
            communication_bus: CommunicationBus,
            agent_type: str = 'event_driven',
            throttle: str = "1s"
    ):
        """Initializes the TradingAgent.

        Args:
            config: Configuration dictionary for the agent.
            data_cache: Shared DataCache instance.
            communication_bus: The communication bus instance.
            agent_type: The type of agent, either 'event_driven' or 'periodic'.
            throttle: The default throttle or period (e.g., "1s", "500ms").
        """
        self.config = config
        self.data_cache = data_cache
        self.trading_client: Optional[AlpacaTrading] = None
        self.communication_bus: Optional[CommunicationBus] = communication_bus
        self._last_execution_time: Optional[datetime] = None

        if agent_type not in ['event_driven', 'periodic']:
            raise ValueError("agent_type must be either 'event_driven' or 'periodic'")

        self.agent_type = agent_type
        self.throttle: timedelta = timedelta(seconds=1)
        self.set_throttle(self.config.get('throttle', throttle))
        self.validate_config()

    async def initialize(self):
        """Hook for subclasses to perform async initialization."""
        pass

    def set_trading_client(self, trading_client: AlpacaTrading):
        self.trading_client = trading_client

    def set_throttle(self, time_str: str):
        """Sets the throttle for an event-driven agent or the period for a periodic agent."""
        self.throttle = _parse_time_string(time_str)
        logger.info(f"[{self.__class__.__name__}] Throttle was set to {self.throttle}.")

    async def start(self, data: Any):
        """Entry point for event-driven execution. Enforces throttling."""
        if self.agent_type == 'periodic':
            return

        now = datetime.utcnow()

        if self._last_execution_time and (now - self._last_execution_time) < self.throttle:
            return

        await self.run(data)
        self._last_execution_time = now

    @abstractmethod
    async def run(self, data=None):
        """The core logic of the agent."""
        pass

    def validate_config(self):
        """Hook for subclasses to validate their specific configuration."""
        pass
