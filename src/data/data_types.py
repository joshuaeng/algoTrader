from __future__ import annotations
import datetime
from typing import Optional, Dict, Any, Type, TypeVar

T = TypeVar('T', bound='DataObject')


class DataObject:
    """
    A generic, serializable data container for inter-agent communication,
    designed to be flexible and easily extensible.
    """

    def __init__(self, data_type: str, timestamp: Optional[datetime.datetime] = None, data: Optional[Dict[str, Any]] = None):
        """
        Initializes a new DataObject.

        Args:
            data_type (str): A string identifier for the type of data (e.g., 'spot_price', 'volatility').
            timestamp (Optional[datetime.datetime]): The timestamp when the data was created or captured. Defaults to now.
            data (Optional[Dict[str, Any]]): A dictionary to hold the actual data payload.
        """
        self.timestamp = timestamp or datetime.datetime.now()
        self.data_type = data_type
        self.data = data or {}

    @classmethod
    def create(cls: Type[T], data_type: str, **kwargs) -> T:
        """
        Factory method to create a new DataObject with a specific type and data.

        Args:
            data_type (str): The type of the data object.
            **kwargs: The data payload to be stored in the `data` field.

        Returns:
            DataObject: A new instance of DataObject.
        """
        return cls(
            data_type=data_type,
            data=kwargs
        )

    def get(self, key: str, default: Any = None) -> Any:
        """
        Convenience method to access data from the `data` dictionary.

        Args:
            key (str): The key to look for in the data payload.
            default (Any): The default value to return if the key is not found.

        Returns:
            Any: The value associated with the key, or the default value.
        """
        return self.data.get(key, default)

    def __str__(self):
        # Exclude the 'data' dictionary from the main string representation for clarity
        main_info = f"DataObject(data_type='{self.data_type}', timestamp='{self.timestamp}')"
        # Append the data dictionary in a readable format
        data_info = f"\n  Data: {self.data}"
        return main_info + data_info
