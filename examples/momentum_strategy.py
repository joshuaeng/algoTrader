
import asyncio
import sys
from typing import Any, Dict, List
from collections import defaultdict
from loguru import logger

from src.core.communication_bus import CommunicationBus
from src.core.trading_agent import PeriodicAgent
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache
from src.built_in_agents.spotter import Spotter
from src.built_in_agents.performance_tracker import PerformanceTrackerAgent
from src.data.data_types import DataObject


class MomentumAgent(PeriodicAgent):
    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        super().__init__(config, data_cache, communication_bus)
        self.instruments: List[str] = self.config['instruments']
        self.fast_ma_period: int = self.config.get('fast_ma', 10)
        self.slow_ma_period: int = self.config.get('slow_ma', 30)
        self.trade_qty: int = self.config.get('trade_qty', 10)
        
        self.price_history: Dict[str, List[float]] = defaultdict(list)
        self.positions: Dict[str, float] = defaultdict(float)
        self.momentum_is_bullish: Dict[str, bool] = defaultdict(bool)

    async def initialize(self):
        for instrument in self.instruments:
            await self.communication_bus.subscribe_listener(
                f"SPOT_PRICE('{instrument}')",
                self.snap_spot_price
            )

    async def snap_spot_price(self, spot_price: DataObject):
        instrument = spot_price.get("instrument")
        price = spot_price.get("value")
        if instrument and price:
            self.price_history[instrument].append(price)
            self.price_history[instrument] = self.price_history[instrument][-self.slow_ma_period:]

    async def run(self):
        for instrument in self.instruments:
            history = self.price_history[instrument]
            if len(history) < self.slow_ma_period:
                continue

            fast_ma = sum(history[-self.fast_ma_period:]) / self.fast_ma_period
            slow_ma = sum(history) / self.slow_ma_period
            
            currently_bullish = fast_ma > slow_ma
            previously_bullish = self.momentum_is_bullish[instrument]

            is_golden_cross = currently_bullish and not previously_bullish
            is_death_cross = not currently_bullish and previously_bullish
            
            has_position = self.positions[instrument] > 0

            try:
                if is_golden_cross and not has_position:
                    logger.info(f"Golden Cross on {instrument}. Submitting BUY order for {self.trade_qty} shares.")
                    await self.trading_client.submit_market_order(
                        ticker=instrument, qty=self.trade_qty, side='buy'
                    )
                    self.positions[instrument] = self.trade_qty

                elif is_death_cross and has_position:
                    position_qty = self.positions[instrument]
                    logger.info(f"Death Cross on {instrument}. Submitting SELL order for {position_qty} shares.")
                    await self.trading_client.submit_market_order(
                        ticker=instrument, qty=position_qty, side='sell'
                    )
                    self.positions[instrument] = 0
            
            except Exception as e:
                logger.exception(f"Failed to submit order for {instrument}: {e}")
            
            self.momentum_is_bullish[instrument] = currently_bullish


async def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("momentum_strategy.log", rotation="5 MB", level="DEBUG", catch=False)
    
    trading_hub = TradingHub()
    instruments = ["SPY", "QQQ", "IWM"]

    await trading_hub.add_agent(Spotter, {'instruments': instruments, 'throttle': '5s'})
    
    await trading_hub.add_agent(MomentumAgent, {
        'instruments': instruments, 
        'period': '10s',
        'fast_ma': 10,
        'slow_ma': 30,
        'trade_qty': 15
    })

    await trading_hub.add_agent(PerformanceTrackerAgent, {'period': '30s'})

    logger.info("TradingHub started.")
    await trading_hub.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Strategy execution stopped by user.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
