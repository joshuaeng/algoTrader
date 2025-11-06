import asyncio
import datetime
from typing import Dict, Any, List, Optional

from alpaca.trading.models import Position
from loguru import logger

from src.core.data_cache import DataCache
from src.core.trading_agent import TradingAgent


class DeltaHedger(TradingAgent):
    """A TradingAgent that monitors portfolio delta and hedges it.

    This agent periodically checks all open positions, calculates the deviation
    from a target delta, and places limit orders to hedge the difference.
    """

    def __init__(self, config: Dict[str, Any], data_cache: DataCache):
        """Initializes the DeltaHedger agent.

        The configuration dictionary should contain:
        - 'poll_interval': (Optional) How often to run the hedging logic, in seconds. Defaults to 5.0.
        - 'instrument_delta_limit': (Optional) The target delta (in quote currency) for each instrument.
          Defaults to 0.
        """
        super().__init__(config, data_cache)
        self.poll_interval: float = self.config.get('poll_interval', 5.0)
        self.instrument_delta_limit: float = self.config.get('instrument_delta_limit', 0.0)
        self.positions: Optional[List[Position]] = None
        self._last_run_time: Optional[datetime.datetime] = None

        logger.info(f"DeltaHedger agent initialized. Poll interval: {self.poll_interval}s")

    def _update_positions(self):
        """Fetches the latest positions from the trading client."""
        if not self.trading_client:
            return
        try:
            self.positions = self.trading_client.get_all_positions()
        except Exception as e:
            logger.exception(f"DeltaHedger failed to get positions: {e}")
            self.positions = []

    def get_fair_price(self, instrument: str) -> Optional[float]:
        """Retrieves the latest spot price for an instrument from the cache."""
        spot_data = self.data_cache.get(f"_sys/SPOTTER/{instrument}/SPOT")
        return spot_data.fair_price if spot_data else None

    async def start(self, data: Any):
        """Main handler, throttled to run the hedging logic periodically."""
        now = datetime.datetime.utcnow()
        if self._last_run_time and (now - self._last_run_time).total_seconds() < self.poll_interval:
            return  # Throttled
        self._last_run_time = now

        logger.debug("DeltaHedger running hedging logic...")
        self._update_positions()

        if self.positions is None:
            return

        for position in self.positions:
            try:
                market_value = float(position.market_value)
                current_price = float(position.current_price)
                difference = market_value - self.instrument_delta_limit

                if abs(difference) < (current_price * 0.5):  # Avoid tiny, dusty orders
                    continue

                qty = int(difference // current_price)
                side = "sell" if qty > 0 else "buy"
                qty = min(abs(qty), abs(int(position.qty_available)))

                if qty == 0:
                    continue

                # Use cached fair price if available, otherwise use last trade price
                price = self.get_fair_price(instrument=position.symbol) or current_price

                await self._submit_rebalance_order(position.symbol, price, qty, side)

            except Exception as e:
                logger.exception(f"Error during hedging logic for {position.symbol}: {e}")

    async def _submit_rebalance_order(self, ticker, price, qty, side):
        """Helper to submit limit orders and handle errors."""
        if not self.trading_client:
            logger.error("DeltaHedger cannot submit order: trading client not available.")
            return
        try:
            await asyncio.to_thread(
                self.trading_client.submit_limit_order,
                ticker=ticker,
                price=price,
                qty=qty,
                side=side
            )
            logger.success(f"DeltaHedger submitted order: {side} {qty} {ticker} @ {price}")
        except Exception as e:
            logger.exception(f"DeltaHedger failed to submit order for {ticker}: {e}")