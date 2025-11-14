import asyncio
from typing import Optional, Any, Dict

from loguru import logger

from src.built_in_agents.delta_hedger import DeltaHedger
from src.core.trading_agent import TradingAgent
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache
from src.built_in_agents.spotter import Spotter
from src.built_in_agents.spread_calculator import SpreadCalculator
from src.data.data_types import DataObject

# --- Configuration ---
INSTRUMENTS = ["AAPL", "MSFT"]


class Quoter(TradingAgent):
    """
    A simple periodic agent that calculates quotes.
    """
    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus, **kwargs):
        super().__init__(config, data_cache, communication_bus, agent_type='periodic', **kwargs)
        self.last_spot: Dict[str, DataObject] = {}
        self.last_spread: Dict[str, DataObject] = {}

    async def initialize(self):
        for instrument in INSTRUMENTS:
            await self.communication_bus.subscribe_listener(
                f"SPOT_PRICE('{instrument}')",
                self.snap_spot_price
            )
            await self.communication_bus.subscribe_listener(
                f"SPREAD('{instrument}')",
                self.snap_spread
            )

    async def snap_spot_price(self, topic: str, spot_price: DataObject):
        instrument = topic.split("'")[1]
        self.last_spot[instrument] = spot_price

    async def snap_spread(self, topic: str, spread: DataObject):
        instrument = topic.split("'")[1]
        self.last_spread[instrument] = spread

    async def run(self, data=None):
        for instrument in INSTRUMENTS:
            spot_price = self.last_spot.get(instrument)
            spread = self.last_spread.get(instrument)

            if spot_price and spread:
                fair_value = spot_price.get('value')
                spread_value = spread.get('value')

                if fair_value and spread_value:
                    bid_price = fair_value - (fair_value * spread_value / 2)
                    ask_price = fair_value + (fair_value * spread_value / 2)

                    quote_data = DataObject.create(
                        'quote',
                        bid=bid_price,
                        ask=ask_price
                    )
                    await self.communication_bus.publish(f"QUOTE('{instrument}')", value=quote_data)
                    logger.info(f"Published quote for {instrument}: Bid={bid_price:.2f}, Ask={ask_price:.2f}")


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
    quoter_config = {'throttle': '5s'}

    # 3. Instantiate and add built_in_agents to the hub
    # Event-driven built_in_agents
    await trading_hub.add_agent(
        Spotter(config=spotter_config, data_cache=shared_cache, communication_bus=trading_hub.communication_bus)
    )
    await trading_hub.add_agent(
        SpreadCalculator(config=spread_calc_config, data_cache=shared_cache, communication_bus=trading_hub.communication_bus)
    )

    # Periodic built_in_agents
    await trading_hub.add_agent(DeltaHedger(config=delta_hedger_config, data_cache=shared_cache, communication_bus=trading_hub.communication_bus))
    await trading_hub.add_agent(Quoter(config=quoter_config, data_cache=shared_cache, communication_bus=trading_hub.communication_bus))

    # 4. Start the hub. This will run until interrupted.
    await trading_hub.start()


if __name__ == "__main__":
    asyncio.run(main())
