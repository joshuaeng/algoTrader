from enum import Enum

from src.algo_toolkit.algo import Algo
from typing import Optional, Dict, List
from loguru import logger
import dataclasses
import asyncio
import datetime

from src.algo_toolkit.data_cache import DataCache
from src.alpaca_wrapper.market_data import AlpacaMarketData


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
    INSTRUMENT: str
    TIMESTAMP: datetime.datetime = None
    FAIR_PRICE: float = None
    RAW_ORDER_BOOK: List[Quote] = None


class FairPriceMethod(Enum):
    VWAP = "VWAP"
    CROSSED_VWAP = "CROSSED_VWAP"
    MID = "MID"


class Spotter(Algo):
    """Spotter algorithm for concurrent spot price discovery across a list of instruments."""

    def __init__(
        self,
        market_data_client: AlpacaMarketData,
        instruments: List[str],
        cache: DataCache,
        update_freq: float = 1.0,
        fair_price_method: FairPriceMethod = FairPriceMethod.CROSSED_VWAP
    ):
        """Initializes the Spotter algo.

        Args:
            market_data_client (AlpacaMarketData): Market data client.
            instruments (List[str]): List of instrument symbols to monitor.
            update_freq (float, optional): Minimum time interval between processed quotes
                per instrument, in seconds. Defaults to 1.0.
        """
        super().__init__(cache=cache, market_data_client=market_data_client)

        if not instruments:
            raise ValueError("Instrument list cannot be empty.")

        self.instruments = instruments
        self.update_freq = update_freq
        self.fair_price_method = fair_price_method

        # Per-instrument throttling state
        self._last_update_time: Dict[str, datetime.datetime] = {}
        self._locks: Dict[str, asyncio.Lock] = {
            instrument: asyncio.Lock() for instrument in instruments
        }

        logger.info(
            f"Spotter initialized for {len(instruments)} instruments. "
            f"Update frequency is {update_freq}s. "
            f"Fair price is calculated with method: {self.fair_price_method}"

        )

    def calculate_fair_price(self, quote: Quote):
        if self.fair_price_method == FairPriceMethod.CROSSED_VWAP:
            return quote.crossed_vwap

        elif self.fair_price_method == FairPriceMethod.VWAP:
            return quote.vwap

        else:
            return quote.mid

    async def on_new_quote(self, instrument: str, data):
        """Callback executed whenever a new market quote arrives for an instrument.

        Throttles quote processing per instrument to ensure updates
        are handled at a controlled frequency.

        Args:
            instrument (str): Instrument symbol.
            data (dict): Raw market quote data as received from the data stream.

        Returns:
            None
        """
        now = datetime.datetime.utcnow()
        lock = self._locks[instrument]

        async with lock:
            last_update = self._last_update_time.get(instrument)
            if last_update is not None:
                elapsed = (now - last_update).total_seconds()
                if elapsed < self.update_freq:
                    logger.debug(
                        f"[{instrument}] Quote skipped (elapsed={elapsed:.3f}s < {self.update_freq}s)"
                    )
                    return
            self._last_update_time[instrument] = now

        try:
            quote = Quote.init_from_data(data)
            fair_price = self.calculate_fair_price(quote)
            spot_price = SpotPrice(
                    INSTRUMENT=instrument,
                    TIMESTAMP=now,
                    FAIR_PRICE=fair_price,
                    RAW_ORDER_BOOK=[quote],
                )

            self.cache.set(f"_sys/SPOTTER/{instrument}/SPOT", value=spot_price)

            logger.info(
                f"[{instrument}] Processed quote at {now.isoformat()} | "
                f"Fair Price: {fair_price:.4f}"
            )

        except Exception as e:
            logger.exception(f"[{instrument}] Error processing quote: {e}")

    async def start(self):
        """Start the Spotter and subscribe to all market data streams.

        Raises:
            ValueError: If instrument list is empty.

        Returns:
            None
        """
        if not self.instruments:
            raise ValueError("No instruments configured.")

        logger.info(f"Starting Spotter for instruments: {', '.join(self.instruments)}")

        try:
            self.alpaca_market_data.subscribe_stock_quotes(self.on_new_quote, *self.instruments)
            await self.alpaca_market_data.start_streams()
            logger.success(
                f"Spotter stream started for {len(self.instruments)} instruments."
            )

        except Exception as e:
            logger.exception(f"Failed to start Spotter streams: {e}")
