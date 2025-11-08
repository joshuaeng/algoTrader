import threading


class DataCache:
    """A thread-safe, path-based, in-memory cache.

    This class provides a dictionary-like store that is safe for access from
    multiple concurrent asyncio tasks.
    """

    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def set(self, path: str, value):
        """Set a value at a nested path, creating intermediate dicts as needed."""
        with self._lock:
            keys = path.split("/")
            d = self._cache
            for key in keys[:-1]:
                d = d.setdefault(key, {})
            d[keys[-1]] = value

    def get(self, path: str, default=None):
        """Get a value at a nested path, return default if any key is missing."""
        with self._lock:
            keys = path.split("/")
            d = self._cache
            for key in keys:
                if not isinstance(d, dict) or key not in d:
                    return default
                d = d[key]
            return d

    def exists(self, path: str) -> bool:
        """Check if a nested path exists."""
        # This method is safe because it calls self.get(), which is locked.
        return self.get(path, default=None) is not None

    def delete(self, path: str) -> bool:
        """Delete a value at a nested path. Returns True if deleted, False if not found."""
        with self._lock:
            keys = path.split("/")
            d = self._cache
            for key in keys[:-1]:
                if key not in d or not isinstance(d[key], dict):
                    return False
                d = d[key]
            return d.pop(keys[-1], None) is not None