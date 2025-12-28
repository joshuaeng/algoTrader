import asyncio
from src.alpaca_wrapper.base import AlpacaConnector
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError


class AlpacaTrading(AlpacaConnector):
    def __init__(self):
        super().__init__()
        self.client = TradingClient(self.api_key, self.secret_key, paper=self.paper)

    async def get_account(self):
        try:
            return await asyncio.to_thread(self.client.get_account)
        except APIError as e:
            print(f"Error getting account information: {e}")
            raise e

    async def get_all_positions(self):
        try:
            return await asyncio.to_thread(self.client.get_all_positions)
        except APIError as e:
            print(f"Error getting all positions: {e}")
            raise e

    async def submit_market_order(self, ticker: str, qty: float, side: str):
        try:
            market_order_data = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
                time_in_force=TimeInForce.GTC
            )
            return await asyncio.to_thread(self.client.submit_order, order_data=market_order_data)
        except APIError as e:
            print(f"Error submitting market order for {ticker}: {e}")
            raise e

    async def submit_limit_order(self, ticker: str, price: float, qty: float, side: str):
        try:
            limit_order_data = LimitOrderRequest(
                limit_price=price,
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL,
                time_in_force=TimeInForce.GTC
            )
            return await asyncio.to_thread(self.client.submit_order, order_data=limit_order_data)
        except APIError as e:
            print(f"Error submitting limit order for {ticker}: {e}")
            raise e

    async def cancel_order(self, order_id: str):
        return await asyncio.to_thread(self.client.cancel_order_by_id, order_id)

    async def get_all_orders(self):
        try:
            return await asyncio.to_thread(self.client.get_orders)
        except APIError as e:
            print(f"Error getting all orders: {e}")
            raise e