# Trading Algo Framework

A flexible, event-driven, multi-agent framework for building algorithmic trading strategies using the Alpaca API.

## Key Features

- **Multi-Agent Architecture**: Build your strategy by combining independent, reusable agents.
- **Event-Driven**: Agents communicate through an event bus, reacting to market data or other internal events.
- **Hybrid Agent Support**: Supports both event-driven agents (reacting to market data) and periodic agents (running on a schedule).
- **Extensible**: Easily create your own custom agents to encapsulate specific logic.
- **Alpaca Integration**: Connects to Alpaca for market data streams and trade execution.
- **Live Performance Tracking**: Includes a built-in agent for live PnL tracking with graphical visualization.

## Core Concepts

- **Trading Hub**: The central engine that manages the lifecycle of agents, and orchestrates the flow of data.
- **EventDrivenAgent**: A base class for agents that react to market data events. The frequency of execution is controlled by a `throttle`.
- **PeriodicAgent**: A base class for agents that run on a fixed schedule. The execution frequency is controlled by a `period`.
- **Communication Bus**: A publish-subscribe system that allows agents to communicate with each other in a decoupled manner. Agents can publish events and subscribe to listen to events from other agents.
- **DataObject**: A standardized container for data flowing through the communication bus.

## Installation

You can install the `trading-algo` package directly from PyPI:

```bash
pip install trading-algo
```

### Prerequisites

- Python 3 3.9+

## Configuration

This framework requires Alpaca API keys to connect to the market. You can provide these in two ways:

1.  **Environment Variables (Recommended for Production):**
    Set `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` in your environment. The `TradingHub` will automatically pick these up if no keys are explicitly provided.

2.  **Directly to `TradingHub` (Recommended for Examples/Development):**
    You can pass your API key and secret directly when initializing the `TradingHub`:

    ```python
    from trading_algo import TradingHub
    trading_hub = TradingHub(api_key="YOUR_API_KEY", secret_key="YOUR_SECRET_KEY", paper=True)
    ```
    For examples, you might read these from a local `config.ini` file (as shown in the examples) or other local configuration.

## Usage

The main entry point for a strategy is a script where you instantiate a `TradingHub`, add your desired agents, and start the hub.

Here's an example demonstrating a simple multi-agent strategy:

```python
# examples/multi_agent_strategy.py

import asyncio
import os
import configparser
from loguru import logger

from trading_algo import TradingHub, Spotter, SpreadCalculator, DeltaHedger, Quoter, PerformanceTrackerAgent

async def main():
    """Main function to set up and run the algorithm."""
    logger.remove()
    logger.add("multi_agent_strategy.log", rotation="5 MB", level="DEBUG", catch=False)
    logger.add(sys.stderr, level="INFO")
    logger.info("Setting up the TradingHub and its agents.")

    # --- API Key Configuration ---
    # For examples, we'll try to read from config.ini first, then environment variables.
    # In a production setup, environment variables are recommended.
    api_key = os.getenv("APCA_API_KEY_ID")
    secret_key = os.getenv("APCA_API_SECRET_KEY")
    paper_trading = True # Set to False for live trading

    if not api_key or not secret_key:
        config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.ini')
        if os.path.exists(config_path):
            config.read(config_path)
            try:
                api_key = config['alpaca']['api_key']
                secret_key = config['alpaca']['secret_key']
                logger.info("Alpaca API keys loaded from config.ini")
            except KeyError:
                logger.warning("API keys not found in config.ini. Please ensure [alpaca] section with api_key and secret_key exists.")
        else:
            logger.warning("config.ini not found. Attempting to use environment variables.")

    if not api_key or not secret_key:
        logger.error("Alpaca API keys not found in config.ini or environment variables (APCA_API_KEY_ID, APCA_API_SECRET_KEY). Please provide them.")
        return

    # 1. Initialize the core components
    trading_hub = TradingHub(api_key=api_key, secret_key=secret_key, paper=paper_trading)

    # 2. Define the instruments to trade
    instruments = ["AAPL", "MSFT"]

    # 3. Instantiate and add agents to the hub
    await trading_hub.add_agent(Spotter, {'instruments': instruments, 'throttle': '5s'})
    await trading_hub.add_agent(SpreadCalculator, {'instruments': instruments, 'throttle': '200ms'})
    await trading_hub.add_agent(DeltaHedger, {'period': '30s'})
    await trading_hub.add_agent(Quoter, {'instruments': instruments, 'period': '5s'})
    await trading_hub.add_agent(PerformanceTrackerAgent, {'period': '30s'}) # Added performance tracker

    # 4. Start the hub. This will run until interrupted.
    await trading_hub.start()


if __name__ == "__main__":
    asyncio.run(main())
```

To run the example strategy, execute the following command from the project root:

```bash
python examples/multi_agent_strategy.py
```

## Creating a Custom Agent

You can easily create your own agents by inheriting from `EventDrivenAgent` or `PeriodicAgent`. The example below shows a simple `PeriodicAgent` that calculates and publishes a quote.

```python
from trading_algo import PeriodicAgent, DataObject

class MyCustomQuoter(PeriodicAgent): # Renamed class to avoid conflict with example
    """
    A simple periodic agent that calculates and publishes quotes.
    """
    def __init__(self, config, data_cache, communication_bus):
        # Pass a 'period' for periodic execution
        super().__init__(config, data_cache, communication_bus, period='5s')
        self.last_spot_price = None

    async def initialize(self):
        # Subscribe to spot price events from other agents
        await self.communication_bus.subscribe_listener(
            "SPOT_PRICE('AAPL')",
            self.on_spot_price
        )

    async def on_spot_price(self, spot_price: DataObject):
        # Store the latest spot price
        self.last_spot_price = spot_price.get('value')

    async def run(self):
        # Core logic for the periodic agent
        if self.last_spot_price:
            # Calculate bid/ask
            bid_price = self.last_spot_price * 0.99
            ask_price = self.last_spot_price * 1.01
            
            # Publish the new quote on the communication bus
            quote_data = DataObject.create('quote', bid=bid_price, ask=ask_price)
            await self.communication_bus.publish("QUOTE('AAPL')", value=quote_data)
            print(f"Published quote for AAPL: Bid={bid_price:.2f}, Ask={ask_price:.2f}")

```
To use this agent, you would add it to the `TradingHub` in your main script:

```python
await trading_hub.add_agent(MyCustomQuoter, {'period': '5s'})
```