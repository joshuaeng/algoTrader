from datetime import datetime
from typing import Dict, Any, List, Optional

from loguru import logger

from src.core.communication_bus import CommunicationBus
from src.core.data_cache import DataCache
from src.data.data_types import DataObject
from src.core.trading_agent import EventDrivenAgent


class Spotter(EventDrivenAgent):
    """A TradingAgent that calculates the spot price for instruments and caches it."""

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        """Initializes the Spotter agent."""
        super().__init__(config, data_cache, communication_bus)
        # self.instruments: List[str] = self.config['instruments'] # No longer needed here
        # self.fair_price_method: str = self.config.get('fair_price_method', 'crossed_vwap') # No longer needed here

        logger.info(
            f"Spotter initialized for {len(self.config['instruments'])} instruments. "
            f"Fair price is calculated with method: {self.config.get('fair_price_method', 'crossed_vwap')}"
        )

    def validate_config(self):
        """Validates the 'instruments' key in the config."""
        if 'instruments' not in self.config or not self.config['instruments']:
            raise ValueError("Spotter config requires a non-empty 'instruments' list.")

    async def initialize(self):
        """Hook for subclasses to perform async initialization."""
        if self.hub:
            await self.hub.subscribe(self, "quotes", self.config['instruments'])
        else:
            logger.error("Spotter agent not attached to a hub, cannot subscribe to quotes.")

    def _calculate_fair_price(self, bid_price, ask_price, bid_size, ask_size) -> Optional[float]:
        """Calculates the fair price based on the configured method."""
        fair_price_method = self.config.get('fair_price_method', 'crossed_vwap')
        if fair_price_method == 'crossed_vwap':
            return (bid_price * ask_size + ask_price * bid_size) / (bid_size + ask_size)
        elif fair_price_method == 'vwap':
            return (bid_price * bid_size + ask_price * ask_size) / (bid_size + ask_size)
        else: # mid
            return (bid_price + ask_price) / 2

    async def run(self, data=None):
        """Processes incoming quote data to calculate and cache the spot price."""
        logger.info(f"Spotter received data: {data}")
        instrument = getattr(data, 'symbol', None)
        # The hub now handles filtering, so this check is no longer needed here
        # if not instrument or instrument not in self.instruments:
        #     return

        now = datetime.utcnow()

        try:
            fair_price = self._calculate_fair_price(data.bid_price, data.ask_price, data.bid_size, data.ask_size)

            if fair_price is None:
                logger.warning(f"[{instrument}] Could not calculate fair price from data.")
                return

            spot_price_data = DataObject.create(
                'spot_price',
                value=fair_price,
                instrument=instrument
            )

            await self.communication_bus.publish(f"SPOT_PRICE('{instrument}')", value=spot_price_data)

            logger.info(
                f"[{instrument}] Processed quote at {now.isoformat()} | "
                f"Fair Price: {fair_price:.4f}"
            )

        except Exception as e:
            logger.exception(f"[{instrument}] Error processing quote in Spotter: {e}")