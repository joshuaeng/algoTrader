from loguru import logger
from src.alpaca_wrapper.base import AlpacaConnector
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream, CryptoDataStream, NewsDataStream
from alpaca.data.requests import (
    StockBarsRequest,
    StockQuotesRequest,
    StockTradesRequest,
    StockSnapshotRequest,
    StockLatestQuoteRequest,
    StockLatestTradeRequest,
)
from alpaca.data.timeframe import TimeFrame
import pandas as pd
from alpaca.common.exceptions import APIError


class AlpacaMarketData(AlpacaConnector):
    """
    A wrapper class for the Alpaca Market Data API.

    This class provides methods for retrieving historical and real-time market data from Alpaca.
    """

    def __init__(self):
        """
        Initializes the AlpacaMarketData class.
        """
        super().__init__()
        logger.info("Initializing AlpacaMarketData")
        self.historical_data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        self.stock_stream_client = StockDataStream(self.api_key, self.secret_key)
        self.stock_subscriptions = []
        self.crypto_subscriptions = []
        self.news_subscriptions = []
        logger.info("AlpacaMarketData initialized")

    def get_historical_data(self, ticker: str, timeframe: TimeFrame, start: str, end: str) -> pd.DataFrame:
        """
        Get historical market data for a ticker.

        Args:
            ticker (str): The ticker symbol.
            timeframe (TimeFrame): The timeframe for the data (e.g., TimeFrame.Day, TimeFrame.Hour, TimeFrame.Minute).
            start (str): The start date for the data (YYYY-MM-DD).
            end (str): The end date for the data (YYYY-MM-DD).

        Returns:
            pd.DataFrame: A pandas DataFrame with the historical data.

        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            request_params = StockBarsRequest(
                symbol_or_symbols=[ticker],
                timeframe=timeframe,
                start=start,
                end=end,
            )
            return self.historical_data_client.get_stock_bars(request_params).df
        except APIError as e:
            logger.exception(f"Error getting historical data for {ticker}: {e}")
            raise e

    def get_latest_bar(self, ticker: str) -> pd.Series:
        """
        Get the latest bar data for a ticker.

        Args:
            ticker (str): The ticker symbol.

        Returns:
            pd.Series: A pandas Series with the latest bar data.

        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            request_params = StockBarsRequest(
                symbol_or_symbols=[ticker], timeframe=TimeFrame.Day
            )
            return self.historical_data_client.get_stock_bars(request_params).df.iloc[-1]
        except APIError as e:
            logger.exception(f"Error getting latest bar for {ticker}: {e}")
            raise e

    def get_quotes(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """
        Get historical quote data for a ticker.

        Args:
            ticker (str): The ticker symbol.
            start (str): The start date for the data (YYYY-MM-DD).
            end (str): The end date for the data (YYYY-MM-DD).

        Returns:
            pd.DataFrame: A pandas DataFrame with the historical quote data.

        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            request_params = StockQuotesRequest(symbol_or_symbols=[ticker], start=start, end=end)
            return self.historical_data_client.get_stock_quotes(request_params).df
        except APIError as e:
            logger.exception(f"Error getting quotes for {ticker}: {e}")
            raise e

    def get_trades(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """
        Get historical trade data for a ticker.

        Args:
            ticker (str): The ticker symbol.
            start (str): The start date for the data (YYYY-MM-DD).
            end (str): The end date for the data (YYYY-MM-DD).

        Returns:
            pd.DataFrame: A pandas DataFrame with the historical trade data.

        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            request_params = StockTradesRequest(symbol_or_symbols=[ticker], start=start, end=end)
            return self.historical_data_client.get_stock_trades(request_params).df
        except APIError as e:
            logger.exception(f"Error getting trades for {ticker}: {e}")
            raise e

    def get_latest_quote(self, ticker: str) -> dict:
        """
        Get the latest quote data for a ticker.

        Args:
            ticker (str): The ticker symbol.

        Returns:
            dict: A dictionary with the latest quote data.

        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            request_params = StockLatestQuoteRequest(symbol_or_symbols=[ticker])
            return self.historical_data_client.get_stock_latest_quote(request_params)
        except APIError as e:
            logger.exception(f"Error getting latest quote for {ticker}: {e}")
            raise e

    def get_latest_trade(self, ticker: str) -> dict:
        """
        Get the latest trade data for a ticker.

        Args:
            ticker (str): The ticker symbol.

        Returns:
            dict: A dictionary with the latest trade data.

        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            request_params = StockLatestTradeRequest(symbol_or_symbols=[ticker])
            return self.historical_data_client.get_stock_latest_trade(request_params)
        except APIError as e:
            logger.exception(f"Error getting latest trade for {ticker}: {e}")
            raise e

    def get_snapshot(self, ticker: str) -> dict:
        """
        Get a snapshot of market data for a ticker.

        Args:
            ticker (str): The ticker symbol.

        Returns:
            dict: A dictionary with the snapshot data.

        Raises:
            APIError: If there is an error from the Alpaca API.
        """
        try:
            request_params = StockSnapshotRequest(symbol_or_symbols=[ticker])
            return self.historical_data_client.get_stock_snapshot(request_params)
        except APIError as e:
            logger.exception(f"Error getting snapshot for {ticker}: {e}")
            raise e

    def subscribe_stock_trades(self, handler, *tickers):
        """
        Subscribe to real-time stock trades.

        Args:
            handler (function): The callback function to handle the trade data.
            *tickers (str): The ticker symbols to subscribe to.
        """
        self.stock_subscriptions.extend(tickers)
        self.stock_stream_client.subscribe_trades(handler, *tickers)

    def subscribe_stock_quotes(self, handler, *tickers):
        """
        Subscribe to real-time stock quotes.

        Args:
            handler (function): The callback function to handle the quote data.
            *tickers (str): The ticker symbols to subscribe to.
        """
        logger.info(f"Subscribing to stock quotes for: {tickers}")
        self.stock_subscriptions.extend(tickers)
        self.stock_stream_client.subscribe_quotes(handler, *tickers)
        logger.info("Subscribed to stock quotes")

    def subscribe_stock_bars(self, handler, *tickers):
        """
        Subscribe to real-time stock bars.

        Args:
            handler (function): The callback function to handle the bar data.
            *tickers (str): The ticker symbols to subscribe to.
        """
        self.stock_subscriptions.extend(tickers)
        self.stock_stream_client.subscribe_bars(handler, *tickers)

    async def start_stream(self):
        """
        Starts the real-time data streams.
        """
        logger.info("Starting market data stream")
        await self.stock_stream_client._run_forever()
        logger.info("Market data stream stopped")

