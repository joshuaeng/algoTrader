class DataCache:
    """
    A simple in-memory data cache for storing data for algorithms.
    """

    def __init__(self):
        """
        Initializes the DataCache.
        """
        self._cache = {}

    def put(self, key: str, value):
        """
        Put a value in the cache.

        Args:
            key (str): The key of the value to put.
            value: The value to put in the cache.
        """
        self._cache[key] = value

    def get(self, key: str):
        """
        Get a value from the cache.

        Args:
            key (str): The key of the value to get.

        Returns:
            The value from the cache, or None if the key is not found.
        """
        return self._cache.get(key)

    def has(self, key: str) -> bool:
        """
        Check if a key is in the cache.

        Args:
            key (str): The key to check.

        Returns:
            bool: True if the key is in the cache, False otherwise.
        """
        return key in self._cache

    def remove(self, key: str):
        """
        Remove a value from the cache.

        Args:
            key (str): The key of the value to remove.
        """
        if self.has(key):
            del self._cache[key]

    def clear(self):
        """
        Clear the entire cache.
        """
        self._cache.clear()
