# Multi-Agent Trading Framework

A flexible, event-driven, multi-agent framework for building algorithmic trading strategies using the Alpaca API.

## Key Features

- **Multi-Agent Architecture**: Build your strategy by combining independent, reusable agents.
- **Event-Driven**: Agents communicate through an event bus, reacting to market data or other internal events.
- **Hybrid Agent Support**: Supports both event-driven agents (reacting to market data) and periodic agents (running on a schedule).
- **Extensible**: Easily create your own custom agents to encapsulate specific logic.
- **Alpaca Integration**: Connects to Alpaca for market data streams and trade execution.

## Core Concepts

- **Trading Hub**: The central engine that manages the lifecycle of agents, and orchestrates the flow of data.
- **EventDrivenAgent**: A base class for agents that react to market data events. The frequency of execution is controlled by a `throttle`.
- **PeriodicAgent**: A base class for agents that run on a fixed schedule. The execution frequency is controlled by a `period`.
- **Communication Bus**: A publish-subscribe system that allows agents to communicate with each other in a decoupled manner. Agents can publish events and subscribe to listen to events from other agents.

## Getting Started

### Prerequisites

- Python 3.9+

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Configuration

This framework requires Alpaca API keys to connect to the market.

1.  **Create a `config.ini` file** in the root of the project.

2.  **Add your Alpaca API keys** to the file with the following structure:

    ```ini
    [alpaca]
    api_key = YOUR_API_KEY
    secret_key = YOUR_SECRET_KEY
    ```
    
    Replace `YOUR_API_KEY` and `YOUR_SECRET_KEY` with your actual Alpaca keys. You can specify paper or live trading keys.

## Usage

The main entry point for a strategy is a script where you instantiate a `TradingHub`, add your desired agents, and start the hub.

The example below demonstrates a simple multi-agent strategy:

```python
# examples/multi_agent_strategy.py

import asyncio
from src.core.trading_hub import TradingHub
from src.built_in_agents.spotter import Spotter
from src.built_in_agents.spread_calculator import SpreadCalculator
from src.built_in_agents.delta_hedger import DeltaHedger

async def main():
    """Main function to set up and run the algorithm."""
    
    # 1. Initialize the core components
    trading_hub = TradingHub()

    # 2. Define the instruments to trade
    instruments = ["AAPL", "MSFT"]

    # 3. Add agents to the hub with their configs
    # Event-driven agents
    await trading_hub.add_agent(Spotter, {'instruments': instruments, 'throttle': '5s'})
    await trading_hub.add_agent(SpreadCalculator, {'instruments': instruments, 'throttle': '200ms'})
    
    # Periodic agent
    await trading_hub.add_agent(DeltaHedger, {'period': '30s'})
    
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
from src.core.trading_agent import PeriodicAgent
from src.data.data_types import DataObject

class Quoter(PeriodicAgent):
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
await trading_hub.add_agent(Quoter, {'period': '5s'})
```
