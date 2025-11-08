import asyncio
from typing import Dict, Any, Optional

from loguru import logger

from src.core.trading_agent import TradingAgent
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache

# --- Configuration ---
# For this example, we'll screen a few tech stocks for momentum.
SYMBOLS_TO_SCREEN = ["NVDA", "AMD", "INTC"]


class MomentumScreener(TradingAgent):
    """
    An event-driven agent that watches for large intraday price moves.
    """
    def __init__(self, config: Dict[str, Any], data_cache: DataCache, **kwargs):
        super().__init__(config, data_cache, agent_type='event_driven', **kwargs)
        self.threshold = self.config.get('momentum_threshold_percent', 3.0)
        self.instruments = self.config.get('instruments', [])
        logger.info(f"MomentumScreener watching {self.instruments} for moves > {self.threshold}%.")

    async def run(self, data: Optional[Any] = None):
        """
        This logic assumes it's receiving bar data, which has open and close prices.
        Note: The hub is currently subscribed to quotes, so this agent would need
        the hub to be subscribed to bars to work correctly.
        """
        if not data or not hasattr(data, 'open') or not hasattr(data, 'close'):
            return  # Not bar data, so we can't calculate momentum

        instrument = getattr(data, 'symbol', None)
        if not instrument or instrument not in self.instruments:
            return

        try:
            percent_change = ((data.close - data.open) / data.open) * 100
            if abs(percent_change) > self.threshold:
                logger.warning(
                    f"** MOMENTUM ALERT [{instrument}] ** | "
                    f"Change: {percent_change:.2f}% | "
                    f"Open: {data.open}, Close: {data.close}"
                )
        except ZeroDivisionError:
            return # Open price was zero, ignore
        except Exception as e:
            logger.exception(f"[{instrument}] Error in MomentumScreener: {e}")


async def main():
    """Main function to set up and run the screener."""
    logger.add("momentum_screener.log", rotation="1 MB", level="INFO")
    logger.info("Setting up the Intraday Momentum Screener.")

    shared_cache = DataCache()
    trading_hub = TradingHub(cache=shared_cache)

    screener_config = {
        'instruments': SYMBOLS_TO_SCREEN,
        'momentum_threshold_percent': 2.0, # Alert on a 2% move
        'throttle': '10s' # Don't check more than every 10 seconds per instrument
    }

    # The screener is an event-driven agent by default.
    trading_hub.add_agent(MomentumScreener(config=screener_config, data_cache=shared_cache))

    logger.info("Starting TradingHub. The screener will now watch for momentum alerts.")
    await trading_hub.start()


if __name__ == "__main__":
    asyncio.run(main())
