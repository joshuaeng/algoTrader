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
        self._cache = cache

    @abstractmethod
    async def run(self):
        """
        This is the main method of the algorithm. It should be implemented by
        the child classes.
        """
        pass

    def _get_from_cache(self, key: str):
        """
        Get a value from the cache.

        Args:
            key (str): The key of the value to get.

        Returns:
            The value from the cache, or None if the key is not found.
        """
        return self._cache.get(key)

    def _put_in_cache(self, key: str, value):
        """
        Put a value in the cache.

        Args:
            key (str): The key of the value to put.
            value: The value to put in the cache.
        """
        self._cache.put(key, value)

    def _has_in_cache(self, key: str) -> bool:
        """
        Check if a key is in the cache.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if the key is in the cache, False otherwise.
        """
        return self._cache.has(key)

    def _remove_from_cache(self, key: str):
        """
        Remove a value from the cache.

        Args:
            key (str): The key of the value to remove.
        """
        self._cache.remove(key)

    def _clear_cache(self):
        """
        Clear the entire cache.
        """
        self._cache.clear()