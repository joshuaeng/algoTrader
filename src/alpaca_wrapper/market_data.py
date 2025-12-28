from loguru import logger
from src.alpaca_wrapper.base import AlpacaConnector
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.live import StockDataStream


class AlpacaMarketData(AlpacaConnector):
    """
    A wrapper class for the Alpaca Market Data API.

    This class provides methods for retrieving historical and real-time market data from Alpaca.
    """

    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        """
        Initializes the AlpacaMarketData class.
        """
        super().__init__(api_key, secret_key, paper)
        logger.info("Initializing AlpacaMarketData")
        self.historical_data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        self.stock_stream_client = StockDataStream(self.api_key, self.secret_key)
        self.stock_subscriptions = []
        self.crypto_subscriptions = []
        self.news_subscriptions = []
        logger.info("AlpacaMarketData initialized")

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
        self.stock_subscriptions.extend(tickers)
        self.stock_stream_client.subscribe_quotes(handler, *tickers)

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
