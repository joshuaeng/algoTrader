
import datetime
from typing import Dict, Any, List
import numpy as np

from loguru import logger

from src.core.data_cache import DataCache
from src.data.data_types import Quote, Spread
from src.core.trading_agent import TradingAgent


class SpreadCalculator(TradingAgent):
    """A TradingAgent that calculates the bid-ask spread for instruments and caches it."""

    def __init__(self, config: Dict[str, Any], data_cache: DataCache):
        """Initializes the SpreadCalculator agent.

        The configuration dictionary should contain:
        - 'instruments': A list of instrument symbols to monitor.

        Args:
            config: The configuration dictionary for the agent.
            data_cache: The shared DataCache instance.
        """
        super().__init__(config, data_cache)
        self.instruments: List[str] = self.config['instruments']
        self.min_data_size: int = self.config.get('min_data_size', 60)

        logger.info(
            f"SpreadCalculator manipulator initialized for {len(self.instruments)} instruments."
        )

    def validate_config(self):
        """Validates the 'instruments' key in the config."""
        if 'instruments' not in self.config or not self.config['instruments']:
            raise ValueError("SpreadCalculator config requires a non-empty 'instruments' list.")

    async def start(self, data: Any):
        """Processes incoming quote data to calculate and cache the spread."""
        instrument = getattr(data, 'symbol', None)
        if not instrument or instrument not in self.instruments:
            return

        now = datetime.datetime.utcnow()

        try:
            quote = Quote.init_from_data(data)
            spread_value = quote.spread
            spreads: list = self.data_cache.get(f"_sys/SPREADS/{instrument}/SPREAD_VALUES")

            if len(spreads) > self.min_data_size:
                spread = Spread(
                    instrument=instrument,
                    timestamp=now,
                    value=np.average(spreads)
                )

                logger.debug(
                    f"[{instrument}] Processed quote at {now.isoformat()} | "
                    f"Spread: {spread_value:.4f}"
                )

                self.data_cache.set(f"_sys/SPREADS/{instrument}/SPREAD", value=spread)

            spreads.append(spread_value)
            self.data_cache.set(f"_sys/SPREADS/{instrument}/SPREAD_VALUES", value=spreads)

        except Exception as e:
            logger.exception(f"[{instrument}] Error processing quote in SpreadCalculator: {e}")




