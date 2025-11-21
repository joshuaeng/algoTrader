import asyncio
import sys
from typing import Any, Dict, List

from loguru import logger

from src.built_in_agents.delta_hedger import DeltaHedger
from src.core.communication_bus import CommunicationBus
from src.core.trading_agent import PeriodicAgent
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache
from src.built_in_agents.spotter import Spotter
from src.built_in_agents.spread_calculator import SpreadCalculator
from src.data.data_types import DataObject


class Quoter(PeriodicAgent):
    """
    A simple periodic agent that calculates quotes.
    """

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        super().__init__(config, data_cache, communication_bus)
        self.instruments: List[str] = self.config['instruments']
        self.last_spot: Dict[str, DataObject] = {}
        self.last_spread: Dict[str, DataObject] = {}

    async def initialize(self):
        for instrument in self.instruments:
            await self.communication_bus.subscribe_listener(
                f"SPOT_PRICE('{instrument}')",
                self.snap_spot_price
            )
            await self.communication_bus.subscribe_listener(
                f"SPREAD('{instrument}')",
                self.snap_spread
            )

    async def snap_spot_price(self, spot_price: DataObject):
        self.last_spot[spot_price.get("instrument")] = spot_price

    async def snap_spread(self, spread: DataObject):
        self.last_spread[spread.get("instrument")] = spread

    async def run(self):
        for instrument in self.instruments:
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
    logger.remove()
    logger.add("multi_agent_strategy.log", rotation="5 MB", level="DEBUG", catch=False)
    logger.add(sys.stderr, level="INFO")
    logger.info("Setting up the TradingHub and its agents.")

    # 1. Initialize the core components
    trading_hub = TradingHub()

    # 2. Define the instruments to trade
    instruments = ["AAPL", "MSFT"]

    # 3. Instantiate and add agents to the hub
    await trading_hub.add_agent(Spotter, {'instruments': instruments, 'throttle': '5s'})
    await trading_hub.add_agent(SpreadCalculator, {'instruments': instruments, 'throttle': '200ms'})
    await trading_hub.add_agent(DeltaHedger, {'period': '30s'})
    await trading_hub.add_agent(Quoter, {'instruments': instruments, 'period': '5s'})

    # 4. Start the hub. This will run until interrupted.
    await trading_hub.start()


if __name__ == "__main__":
    asyncio.run(main())
