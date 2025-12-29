import asyncio
from typing import Any, Dict, List, Set
from collections import defaultdict
from loguru import logger

from src.core.trading_agent import PeriodicAgent
from src.core.communication_bus import CommunicationBus
from src.core.data_cache import DataCache
from src.data.data_types import DataObject


class PerformanceTrackerAgent(PeriodicAgent):
    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        super().__init__(config, data_cache, communication_bus, period=config.get('period', '15s'))
        self.initial_order_ids: Set[str] = set()
        self.processed_order_ids: Set[str] = set()
        self.trades: List[Dict[str, Any]] = []
        self.last_prices: Dict[str, float] = {}
        self.pnl_by_symbol: Dict[str, float] = defaultdict(float)
        self.tracked_instruments: Set[str] = set()

    async def initialize(self):
        logger.info("Initializing PerformanceTrackerAgent.")
        try:
            all_orders = await self.trading_client.get_all_orders()
            self.initial_order_ids = {order.id for order in all_orders}
            self.processed_order_ids = {order.id for order in all_orders if order.status == 'filled'}
            logger.info(f"Baselined with {len(self.initial_order_ids)} existing orders. New trades will be tracked.")
        except Exception as e:
            logger.exception(f"Error during PerformanceTrackerAgent initialization: {e}")

    async def snap_spot_price(self, spot_price: DataObject):
        instrument = spot_price.get("instrument")
        price = spot_price.get("value")
        if instrument and price is not None:
            self.last_prices[instrument] = price

    async def run(self):
        logger.debug("PerformanceTrackerAgent running periodic check.")
        try:
            all_orders = await self.trading_client.get_all_orders()
            
            new_filled_orders = [
                order for order in all_orders
                if order.status == 'filled' and order.id not in self.processed_order_ids
            ]

            if new_filled_orders:
                for order in sorted(new_filled_orders, key=lambda o: o.filled_at):
                    await self._process_trade(order)
                    self.processed_order_ids.add(str(order.id))
            
            self._calculate_pnl()
            self._log_performance_summary()

        except Exception as e:
            logger.exception(f"Error during PerformanceTrackerAgent run: {e}")

    async def _process_trade(self, order):
        symbol = order.symbol
        if symbol not in self.tracked_instruments:
            self.tracked_instruments.add(symbol)
            await self.communication_bus.subscribe_listener(f"SPOT_PRICE('{symbol}')", self.snap_spot_price)

        trade = {
            "symbol": symbol,
            "side": order.side,
            "qty": float(order.filled_qty),
            "price": float(order.filled_avg_price)
        }
        self.trades.append(trade)
        logger.info(f"New trade recorded: {trade['side'].upper()} {trade['qty']} {trade['symbol']} @ {trade['price']:.2f}")

    def _calculate_pnl(self):
        self.pnl_by_symbol.clear()
        for trade in self.trades:
            symbol = trade["symbol"]
            current_price = self.last_prices.get(symbol)

            if current_price is None:
                continue

            if trade["side"] == 'buy':
                trade_pnl = (current_price - trade["price"]) * trade["qty"]
            else:
                trade_pnl = (trade["price"] - current_price) * trade["qty"]
            
            self.pnl_by_symbol[symbol] += trade_pnl

    def _log_performance_summary(self):
        total_pnl = sum(self.pnl_by_symbol.values())
        logger.info(f"Strategy PNL: ${total_pnl:,.2f}")