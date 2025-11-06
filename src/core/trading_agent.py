
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.core.data_cache import DataCache
from src.alpaca_wrapper.trading import AlpacaTrading


class TradingAgent(ABC):
    """Abstract base class for trading agents.

    A TradingAgent is an autonomous component that can be registered with a
    TradingHub. It perceives its environment by receiving market data and can
    act upon it by updating a shared cache or executing orders.
    """

    def __init__(self, config: Dict[str, Any], data_cache: DataCache):
        """Initializes the TradingAgent.

        Args:
            config: A dictionary containing configuration parameters for the
                agent.
            data_cache: A reference to the shared DataCache instance for
                storing and retrieving data.
        """
        self.config = config
        self.data_cache = data_cache
        self.trading_client: Optional[AlpacaTrading] = None
        self.validate_config()

    def set_trading_client(self, trading_client: AlpacaTrading):
        """Provides the agent with access to the trading client.

        This method is called by the TradingHub when the agent is added.
        """
        self.trading_client = trading_client

    @abstractmethod
    async def start(self, data: Any):
        """The core method called by the TradingHub to process new market data.

        Args:
            data: The market data object (e.g., a Trade, Quote, or Bar
                object from the streaming client).
        """
        pass

    def validate_config(self):
        """Hook for subclasses to validate their specific configuration.

        This method is called during initialization. Subclasses should override
        this method to perform any configuration validation.
        """
        pass
