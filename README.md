# Event-Driven Trading Framework

This is a Python-based framework for developing and executing event-driven, agent-based trading algorithms using the Alpaca API.

The core design is built around a central **`TradingHub`** that streams market data and delegates all processing and decision-making to a collection of pluggable **`TradingAgent`** components.

## Core Architecture

The framework is composed of three main components that work together:

1.  **`TradingHub`**: The engine of the framework. It manages the single connection to the market data stream and is responsible for dispatching live data to all registered agents. It also holds the trading client used by agents to execute orders.

2.  **`TradingAgent`**: An autonomous, pluggable component that contains a specific piece of logic. An agent receives data from the `TradingHub` and can perform any task, such as:
    *   **Analysis:** Calculating metrics like fair value or spread.
    *   **Action:** Placing, monitoring, or cancelling orders (e.g., a delta-hedging agent).
    *   **State Management:** Updating the shared data cache.

3.  **`DataCache`**: A simple in-memory, thread-safe dictionary for sharing state between agents and the main trading logic. For example, the `Spotter` agent calculates a fair price and stores it in the cache, where the `DeltaHedger` agent or your main logic can then retrieve it.

The data flows in a clear, one-way direction:

`Market Data -> TradingHub -> (All TradingAgents) -> DataCache -> Your Logic`

## The Philosophy: Layering Logic with Agents

Think of building a trading strategy like managing a team of specialists. Instead of one person trying to do everything, you have a team where each member has a specific job. This framework is designed to work the same way.

The `TradingHub` is the team manager. It receives raw information (market data) and passes it to every specialist (`TradingAgent`) on the team simultaneously. Each agent is a "layer" of logic that processes the information and adds its own insight.

#### An Example: A Market-Making Strategy

Imagine a simple market-making bot. You could build it by layering these agents:

*   **Layer 1: The `Spotter` Agent.** Its only job is to look at the raw order book data and determine the "true" fair price of the asset. It then writes this price to the `DataCache`.

*   **Layer 2: The `Volatility` Agent.** This agent calculates the market's recent volatility. A volatile market might mean you want a wider, safer spread. It writes the current volatility level to the `DataCache`.

*   **Layer 3: The `Spread` Agent.** This agent reads the volatility from the cache and decides what the bid-ask spread should be. A calm market gets a tight spread, a choppy market gets a wide one. It writes the desired spread to the `DataCache`.

*   **Layer 4: The `QuoteManager` Agent.** This agent reads the fair price (from Layer 1) and the desired spread (from Layer 3) and is responsible for placing and managing the actual buy and sell orders via the `trading_client`.

Your main `trading_logic` loop then becomes very simple: it might just monitor the overall profit and loss by reading from the cache, without needing to know the details of how prices are calculated or orders are placed.

#### Benefits of this Approach

*   **Modularity:** Each piece of logic is self-contained. The `Spotter` doesn't need to know how `Volatility` is calculated. This makes the code easier to understand, debug, and test.
*   **Reusability:** The `Spotter` agent you use for this strategy can be dropped into a completely different arbitrage strategy with no changes.
*   **Scalability:** Want to add a new feature, like an agent that manages inventory risk? Just create a new agent and add it to the hub. The existing agents don't need to be modified.

## Project Structure

```
.
├───README.md
├───requirements.txt
├───examples/
│   └───shadow_market_making_algo.py
└───src/
    ├───core/
    │   ├───trading_hub.py
    │   ├───trading_agent.py
    │   ├───data_cache.py
    │   └───exceptions.py
    ├───agents/
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
3.  Set your Alpaca API keys as environment variables. The framework will automatically pick them up.
    ```bash
    export APCA_API_KEY_ID="YOUR_KEY_ID"
    export APCA_API_SECRET_KEY="YOUR_SECRET_KEY"
    ```

## Usage Guide

The `examples/shadow_market_making_algo.py` script provides a complete, up-to-date example of how to use the framework. Here is a breakdown of the key steps.

### 1. Initialize Core Components
First, create instances of the `TradingHub` and the `DataCache`.

```python
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache

shared_cache = DataCache()
trading_hub = TradingHub(cache=shared_cache)
```

### 2. Configure and Add Agents
For each agent, define its configuration and instantiate it, telling the hub whether it is `'event_driven'` or `'periodic'`.

```python
# Define configurations for your built_in_agents
spotter_config = {'instruments': ["AAPL"], 'throttle': '500ms'}
delta_hedger_config = {'throttle': '30s'}

# Instantiate and add built_in_agents to the hub
# Spotter is event-driven by default
trading_hub.add_agent(Spotter(config=spotter_config, data_cache=shared_cache))

# DeltaHedger is periodic by default
trading_hub.add_agent(DeltaHedger(config=delta_hedger_config, data_cache=shared_cache))
```

### 3. Start the Hub
The `TradingHub` manages the entire lifecycle of all agents and data streams. The `start()` method is a blocking call that will run until your application is interrupted.

```python
import asyncio

async def main():
    # ... (setup code from previous steps) ...

    # Start the hub. This will run forever.
    await trading_hub.start()

if __name__ == "__main__":
    asyncio.run(main())
```

This design removes the need for manual task management. Your application's logic is now fully contained within your custom agents.

## The TradingAgent

### Agent Types

There are two types of agents, specified by the `agent_type` parameter during instantiation:

1.  **`'event_driven'` (Default)**: These agents react to market data. Their execution rate is controlled by the `'throttle'` configuration, which sets the *minimum time between runs*.
2.  **`'periodic'`**: These agents run on a fixed schedule. Their execution rate is controlled by the `'throttle'` configuration, which sets the *exact period between runs*.

Some agents, like `DeltaHedger`, are periodic by nature and will override the `agent_type` you provide.

### Concurrency and Performance
The `TradingHub` runs each agent concurrently. When new market data arrives, the hub creates a separate asynchronous task for each event-driven agent. Periodic agents each run in their own parallel loop. This ensures that a slow or throttled agent will **not** block or delay any other agent.

### Available Agents

This framework comes with a few pre-built agents:

| Agent | Default Type | Description | Key Configuration |
| :--- | :--- | :--- | :--- |
| **`Spotter`** | Event-Driven | Calculates a fair price from quote data. | `instruments`, `throttle` |
| **`SpreadCalculator`**| Event-Driven | Calculates a rolling average of the bid-ask spread. | `instruments`, `throttle` |
| **`DeltaHedger`** | Periodic | Monitors and hedges portfolio delta. | `throttle`, `instrument_delta_limit`|

### Creating a Custom Agent

To create your own agent, inherit from `TradingAgent`, implement the `run` method, and be sure to accept `**kwargs` in your `__init__` to pass to the parent class.

#### Event-Driven Agent Example
```python
from src.core.trading_agent import TradingAgent

class MyEventAgent(TradingAgent):
    def __init__(self, config: Dict, data_cache: DataCache, **kwargs):
        # This agent is event-driven by default
        super().__init__(config, data_cache, **kwargs)
        # ... your init logic ...

    async def run(self, data: any):
        # Called for market data events, respecting the 'throttle'.
        print(f"My agent received data: {data}")
```

#### Periodic Agent Example
```python
from src.core.trading_agent import TradingAgent

class MyPeriodicAgent(TradingAgent):
    def __init__(self, config: Dict, data_cache: DataCache, **kwargs):
        # Explicitly set the agent type to 'periodic'
        super().__init__(config, data_cache, agent_type='periodic', **kwargs)
        # ... your init logic ...

    async def run(self, data: Optional[Any] = None):
        # Called every 'throttle' period. 'data' will be None.
        print(f"Running my periodic task!")
```

## Error Handling
The framework includes specific handling for common connection issues. If the application fails to start due to exceeding Alpaca's connection limit, it will log a critical error and raise a `ConnectionLimitExceededError`.

This typically happens if you are running multiple instances of the application with the same API keys.
