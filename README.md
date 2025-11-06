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
    │   └───data_cache.py
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

The `examples/shadow_market_making_algo.py` script provides a complete example of how to use the framework. Here is a step-by-step breakdown.

### 1. Initialize Core Components
First, create instances of the `TradingHub` and the `DataCache` that will be shared across the system.

```python
from src.core.trading_hub import TradingHub
from src.core.data_cache import DataCache

shared_cache = DataCache()
trading_hub = TradingHub(cache=shared_cache)
```

### 2. Configure and Create Agents
For each agent you want to use, define a configuration dictionary and create an instance of it.

```python
from src.agents.spotter import Spotter
from src.agents.spread_calculator import SpreadCalculator

spotter_config = {
    'instruments': ["AAPL"],
    'fair_price_method': 'CROSSED_VWAP'
}
spread_calc_config = {
    'instruments': ["AAPL"],
    'window_size': 100
}

spotter = Spotter(config=spotter_config, data_cache=shared_cache)
spread_calculator = SpreadCalculator(config=spread_calc_config, data_cache=shared_cache)
```

### 3. Add Agents to the Hub
Register each agent with the `TradingHub` instance. The hub will automatically provide the agent with the trading client and subscribe to the required market data.

```python
trading_hub.add_agent(spotter)
trading_hub.add_agent(spread_calculator)
```

### 4. Write Your Core Logic
Your primary trading logic should live in its own `async` function. It typically runs in a loop, reading the latest processed data from the cache (which the agents are populating in the background) and making high-level decisions.

```python
async def trading_logic(hub: TradingHub):
    while True:
        # Read the latest data processed by the agents
        spot_price_data = hub.cache.get("_sys/SPOTTER/AAPL/SPOT")
        spread_data = hub.cache.get("_sys/SPREAD/AAPL/value")

        if spot_price_data and spread_data:
            fair_price = spot_price_data.fair_price
            average_spread = spread_data.value
            
            print(f"Latest Fair Price: {fair_price}, Average Spread: {average_spread}")
            # --- Your decision-making logic goes here ---

        await asyncio.sleep(1) # Loop every second
```

### 5. Start the System
Finally, use `asyncio` to run the `TradingHub` and your `trading_logic` concurrently.

```python
import asyncio

async def main():
    # ... (setup code from previous steps) ...

    # Run the hub in the background
    hub_task = asyncio.create_task(trading_hub.start())

    # Run your logic in the foreground
    logic_task = asyncio.create_task(trading_logic(trading_hub))

    await asyncio.gather(hub_task, logic_task)

if __name__ == "__main__":
    asyncio.run(main())
```

## Available `TradingAgent`s

This framework comes with a few pre-built agents:

| Agent | Description | Configuration Options |
| :--- | :--- | :--- |
| **`Spotter`** | Calculates a fair price for an instrument from quote data. | `instruments` (list), `fair_price_method` (str), `update_freq` (float) |
| **`SpreadCalculator`** | Calculates a rolling average of the bid-ask spread. | `instruments` (list), `window_size` (int), `min_data_size` (int) |
| **`DeltaHedger`** | Periodically monitors and hedges portfolio delta for open positions. | `poll_interval` (float), `instrument_delta_limit` (float) |


## Creating a Custom `TradingAgent`

To create your own agent, simply inherit from the `TradingAgent` base class and implement your logic in the `handle_data` method.

```python
from src.core.trading_agent import TradingAgent

class MyCustomAgent(TradingAgent):
    async def start(self, data: any):
        # This method is called for every data point from the stream
        print(f"My custom agent received data: {data}")

        # --- Your logic here ---
        # You can read from self.data_cache, write to it,
        # or place orders using self.trading_client.
```