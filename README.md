# Trading Algo Framework

This is a Python-based framework for developing and executing automated trading algorithms using the Alpaca API.
To use this framework you first need to create an alpaca account. More information on: https://alpaca.markets/

## Features

*   **Abstract Algo Class:** Provides a framework for creating trading algorithms.
*   **Alpaca API Wrappers:** Includes wrappers for the Alpaca Market Data and Trading APIs.
*   **Real-time Data Streaming:** Supports real-time data streaming for stocks, crypto, and news.
*   **Data Caching:** Includes a simple in-memory data cache for storing data for algorithms.
*   **Configuration:** Uses a `config.ini` file for easy configuration of API keys and other parameters.

## Project Structure

```
.
├── config.ini
├── README.md
├── requirements.txt
└── src
    ├── algo.py
    ├── alpaca_wrapper
    │   ├── base.py
    │   ├── market_data.py
    │   └── trading.py
    └── data_cache.py
```

## Installation

1.  Clone the repository:
    ```
    git clone <repository_url>
    ```
2.  Install the dependencies:
    ```
    pip install -r requirements.txt
    ```

3.  Copy your API and secret key into config.ini.

## Usage

1.  Create a new class that inherits from `Algo` in `main.py` or a separate file.
2.  Implement your trading logic in the `run` method of your new class.
3.  Run your algorithm:
    ```
    python main.py
    ```

## Example

Here is an example of a simple algorithm that subscribes to real-time trades and quotes for the tickers specified in the `config.ini` file:

```python
from src.algo_toolkit.algo import Algo
from src.algo_toolkit.data_cache import DataCache
import asyncio


class MyAlgo(Algo):
    async def run(self):
        tickers = ["SPY", "AAPL"]

        async def on_new_price(data):
            print("New bar data:", data)
            print("Executing algo logic...")

        self.alpaca_market_data.subscribe_stock_bars(handler=on_new_price, tickers=tickers)

        await self.alpaca_market_data.start_streams()


if __name__ == '__main__':
    cache = DataCache()
    algo = MyAlgo(cache=cache)
    asyncio.run(algo.run())
```

