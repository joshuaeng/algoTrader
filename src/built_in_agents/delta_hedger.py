import asyncio
from typing import Dict, Any, List, Optional

from alpaca.trading.models import Position
from loguru import logger

from src.core.communication_bus import CommunicationBus
from src.core.data_cache import DataCache
from src.core.trading_agent import PeriodicAgent
from src.data.data_types import DataObject


class DeltaHedger(PeriodicAgent):
    """A periodic agent that monitors and hedges portfolio delta.

    This agent runs on a fixed schedule (e.g., every 30 seconds), checks
    all open positions, and places orders to hedge any deviation from a
    target delta.
    """

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        """Initializes the DeltaHedger agent.

        The configuration dictionary should contain:
        - 'period': How often to run the hedging logic (e.g., "30s", "1m").
        - 'instrument_delta_limit': (Optional) The target delta in quote currency. Defaults to 0.
        """
        # This agent is periodic by nature.
        super().__init__(config, data_cache, communication_bus)
        self.instrument_delta_limit: float = self.config.get('instrument_delta_limit', 0.0)
        self.positions: Optional[List[Position]] = None
        self.last_spot: Dict[str, DataObject] = {}
        self.instrument_scope: Optional[list] = None

        logger.info(f"DeltaHedger initialized. Running every {self.period}.")

    async def initialize(self):
        """Initial position update."""
        await self._update_positions()
        logger.info("Initial position update done.")

    async def snap_spot(self, topic: str, spot_price: DataObject):
        instrument = topic.split("'")[1]
        self.last_spot[instrument] = spot_price

    async def update_instrument_scope(self):
        self.instrument_scope = [pos.symbol for pos in self.positions]

        for instrument in self.instrument_scope:
            await self.communication_bus.subscribe_listener(f"SPOT_PRICE('{instrument}')", self.snap_spot)

    async def _update_positions(self):
        """Fetches the latest positions from the trading client."""
        if not self.trading_client:
            return
        try:
            self.positions = await self.trading_client.get_all_positions()
            await self.update_instrument_scope()
        except Exception as e:
            logger.exception(f"DeltaHedger failed to get positions: {e}")
            self.positions = []

    def get_spot_price(self, instrument: str) -> Optional[float]:
        """Retrieves the latest spot price for an instrument from the cache."""
        spot_price = self.last_spot.get(instrument, None)
        return spot_price.get('value') if spot_price else None

    async def run(self):
        """Main hedging logic, executed periodically by the TradingHub."""
        logger.debug("DeltaHedger running hedging logic...")
        await self._update_positions()

        if self.positions is None:
            return

        for position in self.positions:
            try:
                market_value = float(position.market_value)
                current_price = float(position.current_price)
                difference = market_value - self.instrument_delta_limit

                if abs(difference) < 0.01:  # Skip if already balanced
                    continue

                qty = int(difference // current_price)
                side = "sell" if qty > 0 else "buy"
                qty = min(abs(qty), abs(int(position.qty_available)))

                if qty == 0:
                    continue

                price = self.get_spot_price(instrument=position.symbol) or current_price
                await self._submit_rebalance_order(position.symbol, price, qty, side)

            except Exception as e:
                logger.exception(f"Error during hedging logic for {position.symbol}: {e}")

    async def _submit_rebalance_order(self, ticker, price, qty, side):
        """Helper to submit limit orders and handle errors."""
        if not self.trading_client:
            logger.error("DeltaHedger cannot submit order: trading client not available.")
            return
        try:
            # The trading client's submit method should be async or run in a thread
            await self.trading_client.submit_limit_order(
                ticker=ticker,
                price=price,
                qty=qty,
                side=side
            )
            logger.success(f"DeltaHedger submitted order: {side} {qty} {ticker} @ {price}")
        except Exception as e:
            logger.exception(f"DeltaHedger failed to submit order for {ticker}: {e}")
