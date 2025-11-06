import asyncio

from loguru import logger

from src.agents.delta_hedger import DeltaHedger
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache
from src.agents.spotter import Spotter
from src.agents.spread_calculator import SpreadCalculator

# --- Configuration ---
INSTRUMENT = "AAPL"


async def trading_logic(hub: TradingHub):
    """This function contains the core trading logic.

    It runs in a loop, reading the latest data from the cache (which is being
    populated by the agents in the background) and then makes decisions.
    """
    logger.info("Trading logic started. Waiting for initial data from agents...")
    # Give agents a moment to populate the cache
    await asyncio.sleep(5)

    while True:
        # --- Read from Cache ---
        # The Spotter and SpreadCalculator are working in the background.
        # Here, we just read the latest results of their work from the cache.
        spot_price_data = hub.cache.get(f"_sys/SPOTTER/{INSTRUMENT}/SPOT")
        spread_data = hub.cache.get(f"_sys/SPREAD/{INSTRUMENT}/value")

        if not spot_price_data or not spread_data:
            logger.warning("Waiting for data to be populated in cache...")
            await asyncio.sleep(5)
            continue

        # --- Make Decisions ---
        # Now you have clean, ready-to-use data.
        fair_price = spot_price_data.fair_price
        current_spread = spread_data.value

        logger.info(f"Latest Data | Fair Price: {fair_price:.4f}, Spread: {current_spread:.4f}")

        # --- Example Action: Place Orders (logic is a placeholder) ---
        # This is where you would implement your market-making logic.
        # For example, you could calculate your bid/ask prices around the fair_price
        # and use the current_spread to inform your quoting strategy.

        # my_bid = fair_price - (current_spread * 0.8)
        # my_ask = fair_price + (current_spread * 0.8)
        #
        # try:
        #     hub.alpaca_trading.submit_limit_order(INSTRUMENT, my_bid, 100, "BUY")
        #     hub.alpaca_trading.submit_limit_order(INSTRUMENT, my_ask, 100, "SELL")
        # except Exception as e:
        #     logger.exception("Failed to submit orders")

        # Wait for the next iteration
        await asyncio.sleep(1)  # Loop every second


async def main():
    """Main function to set up and run the algorithm."""
    logger.add("shadow_mm.log", rotation="5 MB", level="DEBUG")
    logger.info("Setting up the TradingHub and its agents.")

    # 1. Initialize the core components
    shared_cache = DataCache()
    trading_hub = TradingHub(cache=shared_cache)

    # 2. Define configurations for the agents
    spotter_config = {
        'instruments': [INSTRUMENT],
        'fair_price_method': 'CROSSED_VWAP',
        'update_freq': 0.5  # seconds
    }

    spread_calc_config = {
        'instruments': [INSTRUMENT]
    }

    # 3. Instantiate and add agents to the hub
    spotter = Spotter(config=spotter_config, data_cache=shared_cache)
    spread_calculator = SpreadCalculator(config=spread_calc_config, data_cache=shared_cache)
    delta_hedger = DeltaHedger(config={}, data_cache=shared_cache)

    trading_hub.add_agent(spotter)
    trading_hub.add_agent(spread_calculator)
    trading_hub.add_agent(delta_hedger)

    # 4. Start the components
    # The trading_hub will run in the background, feeding data to the agents
    hub_task = asyncio.create_task(trading_hub.start())

    # The trading_logic will run in the foreground, consuming data from the cache
    logic_task = asyncio.create_task(trading_logic(trading_hub))

    # Wait for both tasks to complete (or run forever)
    await asyncio.gather(hub_task, logic_task)


if __name__ == "__main__":
    asyncio.run(main())