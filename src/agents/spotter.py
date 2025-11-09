from datetime import datetime
from typing import Dict, Any, List

from loguru import logger

from src.core.data_cache import DataCache
from src.data.data_types import Quote, SpotPrice, FairPriceMethod
from src.core.trading_agent import TradingAgent


class Spotter(TradingAgent):
    """A TradingAgent that calculates the spot price for instruments and caches it."""

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, **kwargs):
        """Initializes the Spotter agent."""
        super().__init__(config, data_cache, agent_type='event_driven', **kwargs)
        self.instruments: List[str] = self.config['instruments']
        self.fair_price_method: FairPriceMethod = FairPriceMethod(self.config.get('fair_price_method', 'CROSSED_VWAP'))

        logger.info(
            f"Spotter initialized for {len(self.instruments)} instruments. "
            f"Fair price is calculated with method: {self.fair_price_method.value}"
        )

    def validate_config(self):
        """Validates the 'instruments' key in the config."""
        if 'instruments' not in self.config or not self.config['instruments']:
            raise ValueError("Spotter config requires a non-empty 'instruments' list.")

    def calculate_fair_price(self, quote: Quote) -> float:
        """Calculates the fair price based on the configured method."""
        if self.fair_price_method == FairPriceMethod.CROSSED_VWAP:
            return quote.crossed_vwap
        elif self.fair_price_method == FairPriceMethod.VWAP:
            return quote.vwap
        else:
            return quote.mid

    async def run(self, data=None):
        """Processes incoming quote data to calculate and cache the spot price."""
        instrument = getattr(data, 'symbol', None)
        if not instrument or instrument not in self.instruments:
            return

        now = datetime.utcnow()

        try:
            quote = Quote.init_from_data(data)
            fair_price = self.calculate_fair_price(quote)

            if fair_price is None:
                logger.warning(f"[{instrument}] Could not calculate fair price from data.")
                return

            spot_price = SpotPrice(
                instrument=instrument,
                timestamp=now,
                fair_price=fair_price,
                raw_order_book=[quote],
            )

            self.communication_bus.publish(f"SPOT_PRICE('{instrument}')", value=spot_price)

            logger.debug(
                f"[{instrument}] Processed quote at {now.isoformat()} | "
                f"Fair Price: {fair_price:.4f}"
            )

        except Exception as e:
            logger.exception(f"[{instrument}] Error processing quote in Spotter: {e}")

