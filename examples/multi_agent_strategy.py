import asyncio
from typing import Optional, Any, Dict

from loguru import logger

from src.built_in_agents.delta_hedger import DeltaHedger
from src.core.trading_agent import TradingAgent
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache
from src.built_in_agents.spotter import Spotter
from src.built_in_agents.spread_calculator import SpreadCalculator

# --- Configuration ---
INSTRUMENTS = ["AAPL", "MSFT"]


class PortfolioMonitor(TradingAgent):
    """A simple periodic agent that logs the state of the portfolio."""

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, **kwargs):
        super().__init__(config, data_cache, agent_type='periodic', **kwargs)

    async def run(self, data: Optional[Any] = None):
        """Reads from the cache and logs the latest data."""
        logger.info("--- Portfolio Monitor ---")
        for instrument in INSTRUMENTS:
            spot_data = self.data_cache.get(f"_sys/SPOTTER/{instrument}/SPOT")
            spread_data = self.data_cache.get(f"_sys/SPREAD/{instrument}/value")

            if spot_data:
                logger.info(f"[{instrument}] Fair Price: {spot_data.fair_price:.4f}")
            if spread_data:
                logger.info(f"[{instrument}] Avg Spread: {spread_data.value:.4f}")
        logger.info("------------------------")


async def main():
    """Main function to set up and run the algorithm."""
    logger.add("shadow_mm.log", rotation="5 MB", level="DEBUG")
    logger.info("Setting up the TradingHub and its built_in_agents.")

    # 1. Initialize the core components
    shared_cache = DataCache()
    trading_hub = TradingHub(cache=shared_cache)

    # 2. Define configurations for the built_in_agents
    spotter_config = {'instruments': INSTRUMENTS, 'throttle': '500ms'}
    spread_calc_config = {'instruments': INSTRUMENTS, 'throttle': '2s'}
    delta_hedger_config = {'throttle': '30s'}
    monitor_config = {'throttle': '10s'}

    # 3. Instantiate and add built_in_agents to the hub
    # Event-driven built_in_agents
    trading_hub.add_agent(Spotter(config=spotter_config, data_cache=shared_cache))
    trading_hub.add_agent(SpreadCalculator(config=spread_calc_config, data_cache=shared_cache))

    # Periodic built_in_agents
    trading_hub.add_agent(DeltaHedger(config=delta_hedger_config, data_cache=shared_cache))
    trading_hub.add_agent(PortfolioMonitor(config=monitor_config, data_cache=shared_cache))

    # 4. Start the hub. This will run until interrupted.
    await trading_hub.start()


if __name__ == "__main__":
    asyncio.run(main())
