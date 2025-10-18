import asyncio
from abc import ABC, abstractmethod
from src.alpaca_wrapper.market_data import AlpacaMarketData
from src.alpaca_wrapper.trading import AlpacaTrading
from src.data_cache import DataCache


class Algo(ABC):
    """
    An abstract base class for trading algorithms.

    This class provides a framework for creating trading algorithms. It includes
    instances of the AlpacaMarketData and AlpacaTrading classes, as well as a
    data cache for storing data.
    """

    def __init__(self, cache: DataCache):
        """
        Initializes the Algo class.
        """
        self.alpaca_market_data = AlpacaMarketData()
        self.alpaca_trading = AlpacaTrading()
        self.cache = cache

    @abstractmethod
    async def start(self):
        pass




