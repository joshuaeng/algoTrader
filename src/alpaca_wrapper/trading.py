import asyncio
from src.alpaca_wrapper.base import AlpacaConnector
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError
from alpaca.trading.models import Position, Order
from loguru import logger


class AlpacaTrading(AlpacaConnector):
    """
    An asynchronous adapter for the synchronous Alpaca TradingClient.

    This class provides an async interface for trading operations, while internally
    using `asyncio.to_thread` to run the blocking SDK calls in a separate
    thread. This prevents the synchronous calls from blocking the main asyncio
    event loop.
    """
    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        """Initializes the synchronous Alpaca TradingClient."""
        super().__init__(api_key, secret_key, paper)
        self.client = TradingClient(self.api_key, self.secret_key, paper=self.paper)

    async def get_account(self):
        """
        Asynchronously retrieves the current trading account information.

        Returns:
            Account: The account object from the Alpaca API.
        """
        try:
            return await asyncio.to_thread(self.client.get_account)
        except APIError as e:
            print(f"Error getting account information: {e}")
            raise e

    async def get_all_positions(self) -> list[Position]:
        """
        Asynchronously retrieves a list of all open positions.

        Returns:
            list[Position]: A list of position objects.
        """
        try:
            return await asyncio.to_thread(self.client.get_all_positions)
        except APIError as e:
            print(f"Error getting all positions: {e}")
            raise e

    async def submit_market_order(self, ticker: str, qty: float, side: str) -> Order:
        """
        Asynchronously submits a market order.

        Args:
            ticker (str): The ticker symbol for the order.
            qty (float): The quantity to trade.
            side (str): The side of the order ('buy' or 'sell').

        Returns:
            Order: The order object returned after submission.
        """
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

    async def submit_limit_order(self, ticker: str, price: float, qty: float, side: str) -> Order:
        """
        Asynchronously submits a limit order.

        Args:
            ticker (str): The ticker symbol for the order.
            price (float): The limit price for the order.
            qty (float): The quantity to trade.
            side (str): The side of the order ('buy' or 'sell').

        Returns:
            Order: The order object returned after submission.
        """
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
        """
        Asynchronously cancels an open order by its ID.

        Args:
            order_id (str): The unique ID of the order to be canceled.
        """
        return await asyncio.to_thread(self.client.cancel_order_by_id, order_id)

    async def get_all_orders(self) -> list[Order]:
        """
        Asynchronously retrieves a list of all orders.

        Returns:
            list[Order]: A list of order objects.
        """
        logger.debug("Attempting to retrieve all orders from Alpaca.")
        try:
            # Create a GetOrdersRequest to fetch all orders
            orders_request = GetOrdersRequest(status='all', limit=500)
            orders = await asyncio.to_thread(self.client.get_orders, filter=orders_request)
            logger.debug(f"Successfully retrieved {len(orders)} orders.")
            return orders
        except APIError as e:
            logger.error(f"Alpaca API Error while getting all orders: {e}")
            raise e
        except Exception as e:
            logger.error(f"An unexpected error occurred while getting all orders: {e}")
            raise e
