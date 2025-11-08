import asyncio
from typing import Dict, Any, Optional

from loguru import logger

from src.core.trading_agent import TradingAgent
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache


class SimpleLogger(TradingAgent):
    """A minimal periodic agent that logs a message every few seconds."""
    def __init__(self, config: Dict[str, Any], data_cache: DataCache, **kwargs):
        # Explicitly set the agent type to 'periodic'
        super().__init__(config, data_cache, agent_type='periodic', **kwargs)
        logger.info(f"SimpleLogger configured to run every {self.throttle}.")

    async def run(self, data: Optional[Any] = None):
        logger.info("Periodic logger reporting for duty!")


async def main():
    """Main function to set up and run the logger."""
    logger.add("simple_logger.log", rotation="1 MB", level="DEBUG")
    logger.info("Setting up a simple periodic agent.")

    # 1. Initialize the core components
    shared_cache = DataCache()
    trading_hub = TradingHub(cache=shared_cache)

    # 2. Define configuration for the agent
    logger_config = {'throttle': '5s'}

    # 3. Instantiate and add the agent to the hub
    trading_hub.add_agent(SimpleLogger(config=logger_config, data_cache=shared_cache))

    # 4. Start the hub. This will run until interrupted.
    await trading_hub.start()


if __name__ == "__main__":
    asyncio.run(main())
