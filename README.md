# Event-Driven Trading Framework

This is a Python-based framework for developing and executing event-driven, agent-based trading algorithms using the Alpaca API. The framework is built around a central `TradingHub` that streams market data and delegates all processing and decision-making to a collection of pluggable `TradingAgent` components.

## Core Architecture

The framework is composed of three main components:

1.  **`TradingHub`**: The engine of the framework. It manages the connection to the market data stream and dispatches live data to all registered agents.
2.  **`TradingAgent`**: An autonomous, pluggable component that contains a specific piece of logic. Agents can be event-driven or periodic.
3.  **`CommunicationBus`**: A simple pub/sub bus that allows agents to communicate with each other by publishing and subscribing to topics.

At the heart of the framework is the `DataObject`, a generic container for all data that flows through the system. This allows for a flexible and extensible architecture where users can create their own data types and agents without modifying the core framework.

## Project Structure

```
.
├───README.md
├───requirements.txt
├───examples/
│   └───multi_agent_strategy.py
└───src/
    ├───core/
    │   ├───trading_hub.py
    │   ├───trading_agent.py
    │   ├───data_cache.py
    │   └───communication_bus.py
    ├───built_in_agents/
    │   ├───spotter.py
    │   ├───spread_calculator.py
    │   └───delta_hedger.py
    ├───data/
    │   └───data_types.py
    └───alpaca_wrapper/
        ├───base.py
        ├───market_data.py
        └───trading.py
```

## Installation

1.  Clone the repository:
    ```bash
    git clone <repository_url>
    ```
2.  Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Set your Alpaca API keys as environment variables:
    ```bash
    export APCA_API_KEY_ID="YOUR_KEY_ID"
    export APCA_API_SECRET_KEY="YOUR_SECRET_KEY"
    ```

## Usage Guide

The `examples/multi_agent_strategy.py` script provides a complete example of how to use the framework. Here is a breakdown of the key steps:

### 1. Initialize Core Components

```python
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache

shared_cache = DataCache()
trading_hub = TradingHub(cache=shared_cache)
```

### 2. Configure and Add Agents

```python
from src.built_in_agents.spotter import Spotter
from src.built_in_agents.spread_calculator import SpreadCalculator
from src.built_in_agents.delta_hedger import DeltaHedger
from examples.multi_agent_strategy import Quoter

# Define configurations for your agents
spotter_config = {'instruments': ["AAPL", "MSFT"], 'throttle': '500ms'}
spread_calc_config = {'instruments': ["AAPL", "MSFT"], 'throttle': '2s'}
delta_hedger_config = {'throttle': '30s'}
quoter_config = {'throttle': '5s'}

# Instantiate and add agents to the hub
await trading_hub.add_agent(Spotter(config=spotter_config, data_cache=shared_cache, communication_bus=trading_hub.communication_bus))
await trading_hub.add_agent(SpreadCalculator(config=spread_calc_config, data_cache=shared_cache, communication_bus=trading_hub.communication_bus))
await trading_hub.add_agent(DeltaHedger(config=delta_hedger_config, data_cache=shared_cache, communication_bus=trading_hub.communication_bus))
await trading_hub.add_agent(Quoter(config=quoter_config, data_cache=shared_cache, communication_bus=trading_hub.communication_bus))
```

### 3. Start the Hub

```python
import asyncio

async def main():
    # ... (setup code from previous steps) ...
    await trading_hub.start()

if __name__ == "__main__":
    asyncio.run(main())
```

## Creating a Custom Agent

To create your own agent, inherit from `TradingAgent` and implement the `run` method. You can then use the `communication_bus` to subscribe to topics and publish your own data.

```python
from src.core.trading_agent import TradingAgent
from src.data.data_types import DataObject

class MyCustomAgent(TradingAgent):
    def __init__(self, config, data_cache, **kwargs):
        super().__init__(config, data_cache, **kwargs)

    async def initialize(self):
        await self.communication_bus.subscribe_listener("some_topic", self.on_data)

    async def on_data(self, topic: str, data: DataObject):
        # Process data
        pass

    async def run(self, data=None):
        # Agent's main logic
        pass
```
