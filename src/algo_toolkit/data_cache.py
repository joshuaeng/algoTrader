class DataCache:
    def __init__(self):
        # Example structure: dict[str, dict[str, dict[str, int]]]
        self._cache = {}

    def set(self, path: str, value):
        """Set a value at a nested path, creating intermediate dicts as needed."""
        keys = path.split("/")
        d = self._cache
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value

    def get(self, path: str, default=None):
        """Get a value at a nested path, return default if any key is missing."""
        keys = path.split("/")
        d = self._cache
        for key in keys:
            if not isinstance(d, dict) or key not in d:
                return default
            d = d[key]
        return d

    def exists(self, path: str) -> bool:
        """Check if a nested path exists."""
        return self.get(path, default=None) is not None

    def delete(self, path: str) -> bool:
        """Delete a value at a nested path. Returns True if deleted, False if not found."""
        keys = path.split("/")
        d = self._cache
        for key in keys[:-1]:
            if key not in d or not isinstance(d[key], dict):
                return False
            d = d[key]
        return d.pop(keys[-1], None) is not None
