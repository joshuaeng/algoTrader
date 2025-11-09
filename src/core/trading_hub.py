
import asyncio
from typing import List, Set

from loguru import logger

from src.core.communication_bus import CommunicationBus
from src.core.data_cache import DataCache
from src.core.trading_agent import TradingAgent
from src.alpaca_wrapper.market_data import AlpacaMarketData
from src.alpaca_wrapper.trading import AlpacaTrading


class TradingHub:
    """The central engine for a trading strategy."""

    def __init__(self, cache: DataCache = None):
        """Initializes the TradingHub."""
        self.alpaca_market_data: AlpacaMarketData = AlpacaMarketData()
        self.cache = cache if cache else DataCache()
        self.alpaca_trading: AlpacaTrading = AlpacaTrading()
        self.event_agents: List[TradingAgent] = []
        self.periodic_agents: List[TradingAgent] = []
        self._subscribed_quotes: Set[str] = set()
        self.communication_bus = CommunicationBus()

    def add_agent(self, agent: TradingAgent):
        """Adds a trading agent to the hub, sorting it as event-driven or periodic."""
        agent.set_trading_client(self.alpaca_trading)
        agent.set_communication_bus(self.communication_bus)

        if agent.agent_type == 'periodic':
            self.periodic_agents.append(agent)
            logger.info(f"Added periodic agent: {agent.__class__.__name__}")
        else:
            self.event_agents.append(agent)
            if hasattr(agent, 'instruments') and agent.instruments:
                self._subscribed_quotes.update(agent.instruments)
            logger.info(f"Added event-driven agent: {agent.__class__.__name__}")

    async def _aggregate_agent_listeners(self, data):
        """Dispatches market data to all event-driven agents."""
        for agent in self.event_agents:
            asyncio.create_task(agent.start(data))

    @staticmethod
    async def _periodic_agent_loop(agent: TradingAgent):
        """A dedicated loop for running a single periodic agent."""
        logger.info(f"Starting loop for periodic agent '{agent.__class__.__name__}' with period {agent.throttle}.")
        while True:
            try:
                await agent.run()
            except Exception as e:
                logger.exception(f"Error in periodic agent {agent.__class__.__name__}: {e}")
            await asyncio.sleep(agent.throttle.total_seconds())

    async def start(self):
        """
        Starts the trading hub with a supervisor loop.
        If a connection limit error occurs, it will wait and retry.
        """
        if not self.event_agents and not self.periodic_agents:
            logger.warning("No agents added. The trading hub will do nothing.")
            return

        while True:
            periodic_tasks = []
            # Start periodic agent loops
            for agent in self.periodic_agents:
                periodic_tasks.append(asyncio.create_task(self._periodic_agent_loop(agent)))

            # Start market data stream for event-driven agents
            if self.event_agents:
                if not self._subscribed_quotes:
                    logger.warning("No instruments to subscribe to for event-driven agents.")
                else:
                    logger.info(f"Subscribing to quotes for: {list(self._subscribed_quotes)}")
                    self.alpaca_market_data.subscribe_stock_quotes(
                        self._aggregate_agent_listeners, 
                        *list(self._subscribed_quotes)
                    )
                    
                    self.alpaca_market_data.start_stream()

            if not periodic_tasks:
                logger.warning("Hub started but no active periodic tasks to run.")
                return

            logger.success("TradingHub started successfully.")
            await asyncio.gather(*periodic_tasks)
