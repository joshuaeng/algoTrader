import datetime
from typing import Dict, Any, List, Optional
from collections import deque

import numpy as np
from loguru import logger

from src.core.communication_bus import CommunicationBus
from src.core.data_cache import DataCache
from src.data.data_types import DataObject
from src.core.trading_agent import EventDrivenAgent


class SpreadCalculator(EventDrivenAgent):
    """A TradingAgent that calculates a rolling average of the bid-ask spread."""

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        """Initializes the SpreadCalculator agent.

        The configuration dictionary should contain:
        - 'instruments': A list of instrument symbols to monitor.
        - 'window_size': (Optional) The maximum number of recent spreads to keep for the average. Defaults to 100.
        - 'min_data_size': (Optional) The minimum number of spreads required before calculating an average. Defaults to 20.

        Args:
            config: The configuration dictionary for the agent.
            data_cache: The shared DataCache instance.
        """
        super().__init__(config, data_cache, communication_bus)
        # self.instruments: List[str] = self.config['instruments'] # No longer needed here
        self.window_size: int = self.config.get('window_size', 100)
        self.min_data_size: int = self.config.get('min_data_size', 20)

        # In-memory state to hold recent spread values for each instrument
        self.spread_history: Dict[str, deque] = {
            instrument: deque(maxlen=self.window_size) for instrument in self.config['instruments']
        }

        logger.info(
            f"SpreadCalculator agent initialized for {len(self.config['instruments'])} instruments. "
            f"Window size: {self.window_size}, Min data: {self.min_data_size}"
        )

    def validate_config(self):
        """Validates the 'instruments' key in the config."""
        if 'instruments' not in self.config or not self.config['instruments']:
            raise ValueError("SpreadCalculator config requires a non-empty 'instruments' list.")

    async def initialize(self):
        """Hook for subclasses to perform async initialization."""
        if self.hub:
            await self.hub.subscribe(self, "quotes", self.config['instruments'])
        else:
            logger.error("SpreadCalculator agent not attached to a hub, cannot subscribe to quotes.")

    async def run(self, data: Optional[Any] = None):
        """Processes incoming quote data to calculate and cache the rolling average spread."""
        if not data:
            return

        instrument = getattr(data, 'symbol', None)
        # The hub now handles filtering, so this check is no longer needed here
        # if not instrument or instrument not in self.instruments:
        #     return

        now = datetime.datetime.utcnow()

        try:
            bid_price = getattr(data, "bid_price", None)
            ask_price = getattr(data, "ask_price", None)

            if not all([bid_price, ask_price]):
                return

            spread_value = ask_price - bid_price
            mid_price = (ask_price + bid_price) / 2

            if spread_value is None or spread_value <= 0:
                return  # Ignore invalid or zero spreads

            # Get the specific deque for this instrument and add the new value
            history = self.spread_history[instrument]
            history.append(spread_value/mid_price)

            # Only calculate and cache if we have enough data
            if len(history) >= self.min_data_size:
                average_spread = np.average(history)

                spread_data = DataObject.create(
                    'spread',
                    value=average_spread,
                    instrument=instrument
                )

                # Publish the calculated average spread to the cache
                await self.communication_bus.publish(f"SPREAD('{instrument}')", value=spread_data)

                logger.info(
                    f"[{instrument}] Processed quote at {now.isoformat()} | "
                    f"Avg Spread: {average_spread:.4f} (from {len(history)} values)"
                )

        except Exception as e:
            logger.exception(f"[{instrument}] Error in SpreadCalculator: {e}")
