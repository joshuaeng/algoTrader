
import asyncio
from typing import List, Set

from loguru import logger

from src.core.data_cache import DataCache
from src.core.trading_agent import TradingAgent
from src.alpaca_wrapper.market_data import AlpacaMarketData
from src.alpaca_wrapper.trading import AlpacaTrading


class TradingHub:
    """The central trading hub for running a strategy.

    This class acts as the engine for a trading strategy. It manages the connection
    to the market data stream, hosts and runs a series of 'TradingAgent' plugins,
    and dispatches incoming data to them for processing.
    """

    def __init__(self, cache: DataCache = None):
        """Initializes the TradingHub."""
        self.alpaca_market_data: AlpacaMarketData = AlpacaMarketData()
        self.cache = cache if cache else DataCache()
        self.alpaca_trading: AlpacaTrading = AlpacaTrading()
        self.agents: List[TradingAgent] = []
        self._subscribed_quotes: Set[str] = set()

    def add_agent(self, agent: TradingAgent):
        """Adds a trading agent to the hub.

        The hub will collect all unique instrument symbols from its agents
        and subscribe to the necessary data streams.

        Args:
            agent: An instance of a TradingAgent subclass.
        """
        self.agents.append(agent)
        agent.set_trading_client(self.alpaca_trading)
        # Collect instruments to subscribe to
        if hasattr(agent, 'instruments') and agent.instruments:
            self._subscribed_quotes.update(agent.instruments)
        logger.info(f"Added agent: {agent.__class__.__name__}")

    async def _data_handler(self, data):
        """Unified callback for handling all incoming market data.

        This method receives data from the market data stream and passes it
        to all registered agents to be processed concurrently.

        Args:
            data: The data object from the Alpaca stream (e.g., Quote, Trade).
        """
        # Run all agent handlers concurrently for the same piece of data
        await asyncio.gather(
            *[
                agent.start(data)
                for agent in self.agents
            ]
        )

    async def start(self):
        """Starts the trading hub and its data streams.

        This method subscribes to the required market data streams based on the
        instruments specified in the registered agents and starts listening
        for data.
        """
        if not self.agents:
            logger.warning("No agents have been added. The trading hub will not process any data.")
            return

        if not self._subscribed_quotes:
            logger.warning("No instruments to subscribe to. Add agents with instrument lists.")
            return

        logger.info(f"TradingHub starting. Subscribing to quotes for: {list(self._subscribed_quotes)}")

        try:
            self.alpaca_market_data.subscribe_stock_quotes(self._data_handler, *list(self._subscribed_quotes))
            await self.alpaca_market_data.start_streams()
            logger.success("TradingHub streams started successfully.")

        except Exception as e:
            logger.exception(f"Failed to start TradingHub streams: {e}")
