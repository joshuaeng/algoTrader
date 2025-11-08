import asyncio
from typing import Dict, Any, Optional

from loguru import logger

from src.core.trading_agent import TradingAgent
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache
from src.agents.spotter import Spotter

# --- Configuration ---
# We'll look for price differences between Google's two share classes.
# In a real scenario, you might watch a stock and its ADR, or two related ETFs.
ARBITRAGE_PAIR = ["GOOG", "GOOGL"]


class ArbitrageDetector(TradingAgent):
    """
    A periodic agent that detects price discrepancies between two symbols.
    It reads the prices calculated by other agents from the DataCache.
    """
    def __init__(self, config: Dict[str, Any], data_cache: DataCache, **kwargs):
        super().__init__(config, data_cache, agent_type='periodic', **kwargs)
        self.pair = self.config.get('pair', [])
        self.threshold = self.config.get('arbitrage_threshold_usd', 0.50)
        if len(self.pair) != 2:
            raise ValueError("ArbitrageDetector 'pair' config must contain exactly two symbols.")
        logger.info(f"ArbitrageDetector watching {self.pair} for a spread > ${self.threshold}.")

    async def run(self, data: Optional[Any] = None):
        # Get the latest spot prices calculated by the Spotter agents
        spot_a_data = self.data_cache.get(f"_sys/SPOTTER/{self.pair[0]}/SPOT")
        spot_b_data = self.data_cache.get(f"_sys/SPOTTER/{self.pair[1]}/SPOT")

        if not spot_a_data or not spot_b_data:
            logger.debug("Waiting for price data for both symbols...")
            return

        price_a = spot_a_data.fair_price
        price_b = spot_b_data.fair_price
        spread = abs(price_a - price_b)

        logger.debug(f"Checking arbitrage: {self.pair[0]} @ {price_a:.2f} | {self.pair[1]} @ {price_b:.2f} | Spread: ${spread:.2f}")

        if spread > self.threshold:
            logger.warning(
                f"** ARBITRAGE ALERT ** | "
                f"Pair: {self.pair} | "
                f"Spread: ${spread:.2f} (Threshold: ${self.threshold})"
            )


async def main():
    """Main function to set up and run the arbitrage detector."""
    logger.add("arbitrage_detector.log", rotation="1 MB", level="INFO")
    logger.info("Setting up the Price Arbitrage Detector.")

    shared_cache = DataCache()
    trading_hub = TradingHub(cache=shared_cache)

    # --- Agent Configurations ---
    # We need two event-driven Spotter agents to feed prices into the cache.
    spotter_goog_config = {'instruments': ["GOOG"], 'throttle': '500ms'}
    spotter_googl_config = {'instruments': ["GOOGL"], 'throttle': '500ms'}

    # The detector itself is a periodic agent that checks the cache.
    detector_config = {
        'pair': ARBITRAGE_PAIR,
        'arbitrage_threshold_usd': 0.75,  # $0.75 price difference
        'throttle': '2s' # Check every 2 seconds
    }

    # --- Instantiate and Add Agents ---
    # Event-driven agents to provide the data
    trading_hub.add_agent(Spotter(config=spotter_goog_config, data_cache=shared_cache))
    trading_hub.add_agent(Spotter(config=spotter_googl_config, data_cache=shared_cache))

    # The periodic agent that consumes the data
    trading_hub.add_agent(ArbitrageDetector(config=detector_config, data_cache=shared_cache))

    logger.info("Starting TradingHub. The detector will now watch for arbitrage opportunities.")
    await trading_hub.start()


if __name__ == "__main__":
    asyncio.run(main())
