import asyncio
from typing import List, Dict, Any
from alpaca.data.models.bars import Bar
from alpaca.data.models.quotes import Quote
from alpaca.data.models.trades import Trade
from loguru import logger

from src.core.communication_bus import CommunicationBus
from src.core.data_cache import DataCache
from src.core.trading_agent import EventDrivenAgent, PeriodicAgent
from src.alpaca_wrapper.market_data import AlpacaMarketData
from src.alpaca_wrapper.trading import AlpacaTrading


class TradingHub:
    """The central engine for a trading strategy."""

    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = True):
        """Initializes the TradingHub."""
        self.alpaca_market_data: AlpacaMarketData = AlpacaMarketData(api_key, secret_key, paper)
        self.cache = DataCache()
        self.alpaca_trading: AlpacaTrading = AlpacaTrading(api_key, secret_key, paper)
        self.event_agents: List[EventDrivenAgent] = []
        self.periodic_agents: List[PeriodicAgent] = []
        # New subscription structure: channel -> symbol -> [agents]
        self.subscriptions: Dict[str, Dict[str, List[EventDrivenAgent]]] = {
            "quotes": {},
            "trades": {},
            "bars": {}
        }
        self.communication_bus = CommunicationBus()

    async def add_agent(self, agent_class: type, config: dict):
        """Adds a trading agent to the hub, sorting it as event-driven or periodic."""
        agent = agent_class(
            config=config,
            data_cache=self.cache,
            communication_bus=self.communication_bus
        )
        agent.set_trading_client(self.alpaca_trading)
        agent.set_hub(self)  # Set the hub reference for the agent
        await agent.initialize() # Agents now subscribe themselves in initialize()

        if isinstance(agent, PeriodicAgent):
            self.periodic_agents.append(agent)
            logger.info(f"Added periodic agent: {agent.__class__.__name__}")
        elif isinstance(agent, EventDrivenAgent):
            self.event_agents.append(agent)
            logger.info(f"Added event-driven agent: {agent.__class__.__name__}")
        else:
            logger.warning(f"Agent {agent.__class__.__name__} is not an instance of EventDrivenAgent or "
                           f"PeriodicAgent, it will not be run.")

    async def subscribe(self, agent: EventDrivenAgent, channel: str, symbols: List[str]):
        """
        Allows an EventDrivenAgent to subscribe to a specific channel and list of symbols.
        """
        if not isinstance(agent, EventDrivenAgent):
            logger.warning(f"Agent {agent.__class__.__name__} is not an EventDrivenAgent and cannot subscribe to channels.")
            return

        if channel not in self.subscriptions:
            logger.warning(f"Unsupported channel '{channel}' for subscription by {agent.__class__.__name__}.")
            return

        for symbol in symbols:
            if symbol not in self.subscriptions[channel]:
                self.subscriptions[channel][symbol] = []
            if agent not in self.subscriptions[channel][symbol]:
                self.subscriptions[channel][symbol].append(agent)
                logger.info(f"Agent {agent.__class__.__name__} subscribed to {channel} for {symbol}.")

    async def _dispatch_data(self, data: Any):
        """
        Dispatches market data to agents that are subscribed
        to the specific channel and instrument.
        """
        # Determine channel and symbol from the incoming data object
        # This part needs to be robust based on alpaca-py data types
        channel = None
        symbol = None

        # Example: Infer channel and symbol based on common alpaca-py data object attributes
        if hasattr(data, 'symbol'):
            symbol = data.symbol

        if isinstance(data, Quote):
            channel = "quotes"
        elif isinstance(data, Trade):
            channel = "trades"
        elif isinstance(data, Bar):
            channel = "bars"
            
        if not channel or not symbol:
            logger.warning(f"Could not determine channel or symbol for incoming data: {data}")
            return

        if channel in self.subscriptions and symbol in self.subscriptions[channel]:
            logger.debug(f"Dispatching {channel} data for {symbol} to {len(self.subscriptions[channel][symbol])} agents.")
            for agent in self.subscriptions[channel][symbol]:
                asyncio.create_task(agent.start(data))
        else:
            logger.debug(f"No agents subscribed to {channel} for {symbol}.")

    @staticmethod
    async def _periodic_agent_loop(agent: PeriodicAgent):
        """A dedicated loop for running a single periodic agent."""
        logger.info(f"Starting loop for periodic agent '{agent.__class__.__name__}' with period {agent.period}.")
        while True:
            try:
                await agent.run()
            except Exception as e:
                logger.exception(f"Error in periodic agent {agent.__class__.__name__}: {e}")
            await asyncio.sleep(agent.period.total_seconds())

    async def start(self):
        """
        Starts the trading hub with a supervisor loop.
        If a connection limit error occurs, it will wait and retry.
        """
        if not self.event_agents and not self.periodic_agents:
            logger.warning("No agents added. The trading hub will do nothing.")
            return

        tasks = []
        for agent in self.periodic_agents:
            tasks.append(asyncio.create_task(self._periodic_agent_loop(agent)))

        # Collect all unique subscriptions for AlpacaMarketData
        alpaca_subscriptions = {
            "quotes": set(),
            "trades": set(),
            "bars": set()
        }
        for channel, symbols_dict in self.subscriptions.items():
            for symbol in symbols_dict.keys():
                if channel in alpaca_subscriptions:
                    alpaca_subscriptions[channel].add(symbol)

        if any(alpaca_subscriptions.values()):
            logger.info(f"Alpaca Market Data Subscriptions: {alpaca_subscriptions}")

            # Subscribe to Alpaca Market Data based on collected subscriptions
            if alpaca_subscriptions["quotes"]:
                self.alpaca_market_data.subscribe_stock_quotes(
                    self._dispatch_data,
                    *list(alpaca_subscriptions["quotes"])
                )
            if alpaca_subscriptions["trades"]:
                self.alpaca_market_data.subscribe_stock_trades(
                    self._dispatch_data,
                    *list(alpaca_subscriptions["trades"])
                )
            if alpaca_subscriptions["bars"]:
                self.alpaca_market_data.subscribe_stock_bars(
                    self._dispatch_data,
                    *list(alpaca_subscriptions["bars"])
                )

            logger.info("Hub is now waiting for market data...")
            tasks.append(asyncio.create_task(self.alpaca_market_data.start_stream()))
        else:
            logger.warning("No event-driven agents subscribed to any market data channels.")

        if not tasks:
            logger.warning("No agents to run. The trading hub will do nothing.")
            return

        logger.success("TradingHub started successfully.")
        await asyncio.gather(*tasks)