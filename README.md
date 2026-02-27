# Trading Algo Framework

A framework for building algorithmic trading strategies by combining independent agents that talk to each other.

```bash
pip install trading-algo
```
*Python 3.9+*

## What is this?

You build trading strategies by snapping together small agents. Each agent does one thing. They don't talk directly — they broadcast messages and listen for messages they care about.

Think of it like a team:
- One agent watches prices
- Another looks for trades
- Another manages risk
- Another tracks profit/loss

They all work independently but coordinate through messages.

## Quick Example

In the example below, we run a momentum strategy:
- We create a Momentum agent. This agent uses a spot price stream to calculate buy or sell signals.
- We instanciate a TradingHub in paper mode.
- We add a Spotter to the trading hub, calculating spot prices for 'QQQ' and 'AAPL'. These spot prices are published every seconds into the SPOT_PRICE('QQQ') and SPOT_PRICE('AAPL') topics.
- We add the Momentum agent to the trading hub. Running every second.
  

```python
import asyncio
import queue
from collections import defaultdict
from trading_algo import TradingHub, PeriodicAgent, Spotter

class MomentumAgent(PeriodicAgent):
    """Buy when fast MA crosses above slow MA. Sell when opposite."""
    
    def __init__(self, config, data_cache, comm_bus):
        super().__init__(config, data_cache, comm_bus)
        self.instruments = config['instruments']
        self.fast_period = config.get('fast_ma', 10)
        self.slow_period = config.get('slow_ma', 30)
        
        # Store recent prices
        self.price_history = defaultdict(
            lambda: queue.Queue(maxsize=self.slow_period)
        )
        self.position = defaultdict(float)
    
    async def initialize(self):
        # Listen for price updates
        for instrument in self.instruments:
            await self.communication_bus.subscribe_listener(
                f"SPOT_PRICE('{instrument}')",
                self.record_price
            )
    
    async def record_price(self, spot_price):
        instrument = spot_price.get("instrument")
        price = spot_price.get("value")
        
        history = self.price_history[instrument]
        if history.full():
            history.get_nowait()
        history.put_nowait(price)
    
    async def run(self):
        """Check for signals (runs every minute)."""
        for instrument in self.instruments:
            history = list(self.price_history[instrument].queue)
            if len(history) < self.slow_period:
                continue
                
            fast_ma = sum(history[-self.fast_period:]) / self.fast_period
            slow_ma = sum(history) / self.slow_period
            
            # Golden cross = buy
            if fast_ma > slow_ma and self.position[instrument] == 0:
                await self.trading_client.submit_market_order(
                    ticker=instrument, qty=10, side='buy'
                )
                self.position[instrument] = 10
                
            # Death cross = sell
            elif fast_ma < slow_ma and self.position[instrument] > 0:
                await self.trading_client.submit_market_order(
                    ticker=instrument, qty=self.position[instrument], side='sell'
                )
                self.position[instrument] = 0

async def main():
    hub = TradingHub(paper=True)
    
    # Price watcher
    await hub.add_agent(Spotter, {
        'instruments': ['SPY', 'QQQ'],
        'throttle': '1s'
    })
    
    # Strategy
    await hub.add_agent(MomentumAgent, {
        'instruments': ['SPY', 'QQQ'],
        'period': '1m',
        'fast_ma': 50,
        'slow_ma': 100
    })
    
    await hub.start()

asyncio.run(main())
```

## Core Pieces

### TradingHub (the engine)

The TradingHub runs everything:
- Holds all your agents
- Connects to Alpaca for market data
- Routes data to the right agents
- Runs periodic agents on schedule
- Handles errors and reconnections

When you call `hub.start()`, it:
1. Sees what data your agents want
2. Subscribes to Alpaca for that data
3. Starts your periodic agents
4. Sits in a loop, routing data as it arrives

### Two Types of Agents

**EventDrivenAgent** - Runs when data arrives:
```python
class MyAgent(EventDrivenAgent):
    def __init__(self, config, ...):
        super().__init__(config, ..., throttle='1s')
```

**PeriodicAgent** - Runs on a fixed schedule:
```python
class MyAgent(PeriodicAgent):
    def __init__(self, config, ...):
        super().__init__(config, ..., period='1s') 
```

### CommunicationBus (how agents talk)

Agents broadcast messages. They don't call each other directly.

**Publish:**
```python
await self.communication_bus.publish("SPOT_PRICE('AAPL')", price_data)
```

**Subscribe (in initialize()):**
```python
await self.communication_bus.subscribe_listener(
    "SPOT_PRICE('AAPL')", 
    self.handle_price
)

async def handle_price(self, price_data):
    price = price_data.get('value')
```

**Heads up:** When you subscribe, you immediately get the last published value (if any). So you don't wait for the next update.

### DataCache (share data safely)

Thread-safe storage for sharing data between agents. Uses paths like filesystem paths.

```python
# Save something
self.data_cache.set("signals/AAPL/last_signal", "buy")

# Get it back
signal = self.data_cache.get("signals/AAPL/last_signal", default=None)

# Check if exists
if self.data_cache.exists("positions/AAPL"):
    # do something

# Delete
self.data_cache.delete("old/stuff")
```

It's thread-safe, so multiple agents can read/write without crashing.

### DataObject (message wrapper)

All messages should use DataObject for consistency:

```python
# Create
price_data = DataObject.create(
    'spot_price',
    value=150.25,
    instrument='AAPL'
)

# Read
instrument = price_data.get('instrument')
price = price_data.get('value')
```

## Built-in Agents

| Agent | What it does | When it runs |
|-------|--------------|--------------|
| **Spotter** | Calculates fair price from quotes | Event-driven |
| **SpreadCalculator** | Tracks average bid-ask spread | Event-driven |
| **DeltaHedger** | Keeps portfolio delta-neutral | Periodic |
| **PerformanceTracker** | Records trades, calculates PnL | Periodic |
| **MomentumAgent** | Example MA crossover strategy | Periodic |

## Making Your Own Agent

```python
from trading_algo import PeriodicAgent  # or EventDrivenAgent

class MyAgent(PeriodicAgent):
    def __init__(self, config, data_cache, comm_bus):
        super().__init__(config, data_cache, comm_bus)
        # config is what you passed in add_agent()
        self.symbols = config.get('symbols', [])
        self.my_data = {}
    
    async def initialize(self):
        # Subscribe to messages
        for symbol in self.symbols:
            await self.communication_bus.subscribe_listener(
                f"SPOT_PRICE('{symbol}')",
                self.on_price
            )
    
    async def on_price(self, spot_price):
        # Handle incoming messages
        symbol = spot_price.get('instrument')
        price = spot_price.get('value')
        self.my_data[symbol] = price
    
    async def run(self):
        # This runs every 'period' seconds
        # Put your main logic here
        pass
```

## What Agents Have Access To

Every agent gets:
- **`self.communication_bus`** - send/receive messages
- **`self.trading_client`** - place orders, check account
- **`self.data_cache`** - share data between agents
- **`self.config`** - your settings
- **`self.hub`** - the TradingHub (set automatically)

## Configuration

### API Keys (pick one)

**Environment variables** (cleanest):
```bash
export APCA_API_KEY_ID="your-key"
export APCA_API_SECRET_KEY="your-secret"
```

**Pass to TradingHub** (easiest for testing):
```python
hub = TradingHub(api_key="...", secret_key="...", paper=True)
```

### Agent config

```python
await hub.add_agent(MyAgent, {
    'symbols': ['AAPL', 'MSFT'],
    'period': '30s',      # for PeriodicAgent
    'throttle': '1s',     # for EventDrivenAgent
    'anything': 'you want'
})
```

Time strings: `'500ms'`, `'1s'`, `'30s'`, `'1m'`, `'1h'`, `'1d'`

## How Market Data Flows

1. In `initialize()`, your agent subscribes to topics
2. TradingHub tracks all subscriptions
3. When `start()` is called, Hub tells Alpaca what data to send
4. When data arrives, Hub routes it to subscribed agents
5. Your agent's `run(data)` gets called (event-driven) or `run()` gets called (periodic)

