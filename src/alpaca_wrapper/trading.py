from src.alpaca_wrapper.base import AlpacaConnector
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError


class AlpacaTrading(AlpacaConnector):
    """
    A wrapper class for the Alpaca Trading API.

    This class provides methods for interacting with the Alpaca Trading API,
    such as getting account information, managing positions, and submitting orders.
    """

    def __init__(self):
        """
        Initializes the AlpacaTrading class.
        """
        super().__init__()
        self.client = TradingClient(self.api_key, self.secret_key, paper=self.paper)

    def get_account(self):
        """
        Get account information.

        Returns:
            Account: The account object.
        
        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            return self.client.get_account()
        except APIError as e:
            print(f"Error getting account information: {e}")
            raise e

    def get_all_positions(self):
        """
        Get all positions.

        Returns:
            list[Position]: A list of position objects.
        
        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            return self.client.get_all_positions()
        except APIError as e:
            print(f"Error getting all positions: {e}")
            raise e

    def submit_market_order(self, ticker: str, qty: float, side: str):
        """
        Submit a market order.

        Args:
            ticker (str): The ticker symbol.
            qty (float): The quantity to trade.
            side (str): The side of the order ('buy' or 'sell').

        Returns:
            Order: The order object.
        
        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            market_order_data = MarketOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY if side == 'buy' else OrderSide.SELL,
                time_in_force=TimeInForce.GTC
            )
            return self.client.submit_order(order_data=market_order_data)
        except APIError as e:
            print(f"Error submitting market order for {ticker}: {e}")
            raise e

    def submit_limit_order(self, ticker: str, price: float, qty: float, side: str):
        """
        Submit a limit order.

        Args:
            ticker (str): The ticker symbol.
            price (float): The limit price.
            qty (float): The quantity to trade.
            side (str): The side of the order ('buy' or 'sell').

        Returns:
            Order: The order object.

        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            limit_order_data = LimitOrderRequest(
                limit_price=price,
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL,
                time_in_force=TimeInForce.GTC
            )
            return self.client.submit_order(order_data=limit_order_data)
        except APIError as e:
            print(f"Error submitting limit order for {ticker}: {e}")
            raise e

    def cancel_order(self, order_id: str):
        self.client.cancel_order_by_id(order_id)

    def get_all_orders(self):
        """
        Get all orders.

        Returns:
            list[Order]: A list of order objects.
        
        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            return self.client.get_orders()
        except APIError as e:
            print(f"Error getting all orders: {e}")
            raise e
