
import dataclasses
import datetime
from enum import Enum
from typing import Optional, List


class Quote:
    """A lightweight object representing a quote.

    Attributes:
        bid (float): Best bid price.
        ask (float): Best ask price.
        bid_size (float): Bid-side quantity.
        ask_size (float): Ask-side quantity.
    """

    def __init__(self):
        self.bid: Optional[float] = None
        self.ask: Optional[float] = None
        self.bid_size: Optional[float] = None
        self.ask_size: Optional[float] = None

    @classmethod
    def init_from_data(cls, data):
        """Create a Quote instance from raw market data.

        Args:
            data: Market data object or dict with bid/ask fields.

        Returns:
            Quote: Initialized Quote instance.
        """
        obj = cls()
        obj.bid = getattr(data, "bid_price", None)
        obj.ask = getattr(data, "ask_price", None)
        obj.bid_size = getattr(data, "bid_size", None)
        obj.ask_size = getattr(data, "ask_size", None)
        return obj

    @property
    def spread(self) -> Optional[float]:
        """Bid-ask spread (ask - bid)."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    @property
    def vwap(self) -> Optional[float]:
        """Volume-weighted average price (VWAP) across bid and ask sides."""
        if None in (self.bid, self.ask, self.bid_size, self.ask_size):
            return None
        total_qty = self.bid_size + self.ask_size
        return (self.bid * self.bid_size + self.ask * self.ask_size) / total_qty

    @property
    def crossed_vwap(self) -> Optional[float]:
        """A 'crossed' VWAP — weights each side’s price by the opposite side’s quantity."""
        if None in (self.bid, self.ask, self.bid_size, self.ask_size):
            return None
        total_qty = self.bid_size + self.ask_size
        return (self.bid * self.ask_size + self.ask * self.bid_size) / total_qty

    @property
    def mid(self) -> Optional[float]:
        """Midpoint between bid and ask."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return None


@dataclasses.dataclass
class SpotPrice:
    """Container for a computed spot price snapshot."""
    instrument: str
    timestamp: datetime.datetime = None
    fair_price: float = None
    raw_order_book: List[Quote] = None


class FairPriceMethod(Enum):
    """Enum for different methods of calculating fair price."""
    VWAP = "VWAP"
    CROSSED_VWAP = "CROSSED_VWAP"
    MID = "MID"


@dataclasses.dataclass
class Spread:
    """Container for a computed spread snapshot."""
    instrument: str
    timestamp: datetime.datetime = None
    value: float = None
