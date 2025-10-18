import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import numpy as np
from loguru import logger
from alpaca.broker import Order
from alpaca.trading import OrderStatus

from src.algo import Algo
from src.data_cache import DataCache

# --- Quoting Parameters ---
INSTRUMENT_SYMBOL = "AAPL"
QUOTE_FREQ_MS = 500
SPREAD_FACTOR = 0.9
QUANTITY_FACTOR = 0.5
QUOTE_PARAMS_WINDOW_SIZE = 20
QUOTE_PARAMS_AVERAGE_TYPE = "EQUAL_WEIGHTED"

# --- Fair Price Calculation ---
FAIR_PRICE_METHOD = "CROSSED_VWAP"  # Options: "VWAP", "CROSSED_VWAP"
FAIR_PRICE_AVERAGE_TYPE = "EQUAL_WEIGHTED"
FAIR_PRICE_WINDOW_SIZE = 30


class Quote:
    """A lightweight object representing a quote.

    Attributes:
        bid: Best bid price.
        ask: Best ask price.
        bid_quantity: Bid-side quantity.
        ask_quantity: Ask-side quantity.
    """

    def __init__(self):
        self.bid: Optional[float] = None
        self.ask: Optional[float] = None
        self.bid_quantity: Optional[float] = None
        self.ask_quantity: Optional[float] = None

    @classmethod
    def init_from_data(cls, data):
        """Create a Quote from raw market data."""
        obj = cls()
        obj.bid = getattr(data, "bid_price", None)
        obj.ask = getattr(data, "ask_price", None)
        obj.bid_quantity = getattr(data, "bid_size", None)
        obj.ask_quantity = getattr(data, "ask_size", None)
        return obj

    @property
    def spread(self) -> Optional[float]:
        """Return bid-ask spread (ask - bid)."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    @property
    def vwap(self) -> Optional[float]:
        """Volume-weighted average price (VWAP) across bid and ask sides."""
        if None in (self.bid, self.ask, self.bid_quantity, self.ask_quantity):
            return None
        total_qty = self.bid_quantity + self.ask_quantity
        return (self.bid * self.bid_quantity + self.ask * self.ask_quantity) / total_qty

    @property
    def crossed_vwap(self) -> Optional[float]:
        """A 'crossed' VWAP – weights each side’s price by the *opposite* side’s quantity."""
        if None in (self.bid, self.ask, self.bid_quantity, self.ask_quantity):
            return None
        total_qty = self.bid_quantity + self.ask_quantity
        return (self.bid * self.ask_quantity + self.ask * self.bid_quantity) / total_qty

    @property
    def mid(self) -> Optional[float]:
        """Midpoint between bid and ask."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return None


class ShadowMarketMaker(Algo):
    """A simple shadow market-making algorithm.

    This algo listens to incoming quotes, builds a fair value from historical data,
    and posts synthetic quotes using Alpaca's trading API.
    """

    def __init__(self, cache: DataCache):
        super().__init__(cache)
        self.instrument_symbol: Optional[str] = None
        self.start_ts: Optional[datetime] = None
        self.last_quote: Optional[Quote] = None
        self.iter_count = 0

        self.quote_status: Dict[str, Any] = {
            "TIMESTAMP": None,
            "BID_PRICE": None,
            "BID_SIZE": None,
            "ASK_PRICE": None,
            "ASK_SIZE": None,
            "BID_ORDER_ID": None,
            "ASK_ORDER_ID": None,
        }

        logger.info("ShadowMarketMaker initialized.")

    async def on_new_quote(self, data):
        """Callback executed whenever new market data (quote) arrives."""
        self.iter_count += 1
        quote = Quote.init_from_data(data)

        quotes = self.cache.get("QUOTES") or {}
        symbol_quotes = quotes.get(data.symbol, {})
        symbol_quotes[data.timestamp] = quote
        quotes[data.symbol] = symbol_quotes
        self.cache.put("QUOTES", quotes)

        logger.debug(f"Received quote #{self.iter_count} for {data.symbol} at {data.timestamp}.")

        # Start quoting only after enough data points are collected
        if len(symbol_quotes) >= FAIR_PRICE_WINDOW_SIZE:
            logger.info(f"Sufficient data collected for {data.symbol}, xpreparing to send quote...")
            self.send_quote()

    @staticmethod
    def get_last_n_entries(d: Dict, n: int) -> Dict:
        """Return the last n entries from a timestamp-keyed dict."""
        if not d:
            return {}
        sorted_items = sorted(d.items(), key=lambda x: x[0])
        return dict(sorted_items[-n:])

    def calculate_fair_price(self, quotes: Dict) -> Optional[float]:
        """Compute fair value using recent quotes and VWAP logic."""
        quotes_last_n = self.get_last_n_entries(quotes, FAIR_PRICE_WINDOW_SIZE)

        if FAIR_PRICE_METHOD == "CROSSED_VWAP":
            values = [q.crossed_vwap for q in quotes_last_n.values() if q.crossed_vwap]
        else:
            values = [q.vwap for q in quotes_last_n.values() if q.vwap]

        if not values:
            logger.warning("Fair price calculation skipped (no valid VWAP values).")
            return None

        fair_price = np.average(values)
        logger.debug(f"Calculated fair price: {fair_price:.5f} using {len(values)} samples.")
        return fair_price

    def calculate_rolling_spread_and_quantity(self, quotes: Dict) -> Optional[Dict[str, float]]:
        """Compute average spread and side quantities across recent quotes."""
        quotes_last_n = self.get_last_n_entries(quotes, QUOTE_PARAMS_WINDOW_SIZE)
        spreads = [q.spread for q in quotes_last_n.values() if q.spread]
        bid_q = [q.bid_quantity for q in quotes_last_n.values() if q.bid_quantity]
        ask_q = [q.ask_quantity for q in quotes_last_n.values() if q.ask_quantity]

        if not spreads or not bid_q or not ask_q:
            logger.warning("Rolling spread/quantity calculation skipped due to insufficient data.")
            return None

        results = {
            "SPREAD": np.average(spreads),
            "BID_QUANTITY": np.average(bid_q),
            "ASK_QUANTITY": np.average(ask_q),
        }

        logger.debug(
            f"Rolling params: spread={results['SPREAD']:.5f}, "
            f"bid_qty={results['BID_QUANTITY']:.3f}, ask_qty={results['ASK_QUANTITY']:.3f}"
        )
        return results

    def calculate_quote(self, symbol: str) -> Optional[Quote]:
        """Generate a synthetic quote from fair value and averaged market parameters."""
        quotes = self.cache.get("QUOTES").get(symbol, {})
        fair_price = self.calculate_fair_price(quotes)
        params = self.calculate_rolling_spread_and_quantity(quotes)

        if not fair_price or not params:
            logger.debug("Skipping quote generation (missing fair price or params).")
            return None

        quote = Quote()
        quote.bid = fair_price - SPREAD_FACTOR * params["SPREAD"] / 2
        quote.ask = fair_price + SPREAD_FACTOR * params["SPREAD"] / 2
        quote.bid_quantity = QUANTITY_FACTOR * params["BID_QUANTITY"]
        quote.ask_quantity = QUANTITY_FACTOR * params["ASK_QUANTITY"]

        logger.info(
            f"Generated quote for {symbol}: "
            f"BID={quote.bid:.5f} ({quote.bid_quantity:.3f}), "
            f"ASK={quote.ask:.5f} ({quote.ask_quantity:.3f})"
        )
        return quote

    def send_quote(self):
        """Post the calculated bid/ask quotes as limit orders."""
        quote = self.calculate_quote(self.instrument_symbol)
        if not quote:
            logger.warning("Quote not sent — no valid quote available.")
            return

        self.last_quote = quote

        try:
            order_sell: Order = self.alpaca_trading.submit_limit_order(
                self.instrument_symbol, quote.ask, quote.ask_quantity, "SELL"
            )
            order_buy: Order = self.alpaca_trading.submit_limit_order(
                self.instrument_symbol, quote.bid, quote.bid_quantity, "BUY"
            )

            logger.debug("Submitted buy/sell limit orders to Alpaca API.")

            if all(o.status == OrderStatus.ACCEPTED for o in [order_buy, order_sell]):
                self.quote_status.update({
                    "TIMESTAMP": datetime.utcnow(),
                    "BID_PRICE": quote.bid,
                    "BID_SIZE": quote.bid_quantity,
                    "ASK_PRICE": quote.ask,
                    "ASK_SIZE": quote.ask_quantity,
                    "BID_ORDER_ID": order_buy.client_order_id,
                    "ASK_ORDER_ID": order_sell.client_order_id,
                })
                logger.success("Quote orders accepted and recorded successfully.")

        except Exception as e:
            logger.exception(f"Error while sending quote orders: {e}")

    async def start(self):
        """Start the shadow market-making process."""
        if not self.instrument_symbol:
            logger.error("No instrument configured to quote.")
            raise ValueError("No instrument configured to quote.")

        self.start_ts = datetime.utcnow()
        logger.info(f"Starting shadow market maker for {self.instrument_symbol} at {self.start_ts}.")
        self.alpaca_market_data.subscribe_crypto_quotes(self.on_new_quote, self.instrument_symbol)
        await self.alpaca_market_data.start_streams()


if __name__ == "__main__":
    async def main():
        logger.add("shadow_mm.log", rotation="5 MB", level="DEBUG")
        logger.info("Starting ShadowMarketMaker main event loop.")
        cache = DataCache()
        algo = ShadowMarketMaker(cache)
        algo.instrument_symbol = INSTRUMENT_SYMBOL
        await algo.start()

    asyncio.run(main())
