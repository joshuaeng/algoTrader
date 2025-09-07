# Trading Algo Framework

This is a Python-based framework for developing and executing automated trading algorithms using the Alpaca API.

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
├── main.py
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
3.  Create a `config.ini` file and add your Alpaca API keys:
    ```ini
    [DEFAULT]
    TICKERS = SPY,AAPL

    [alpaca]
    api_key = YOUR_API_KEY
    secret_key = YOUR_SECRET_KEY
    ```

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
from src.algo import Algo
import configparser
import asyncio

class MyAlgo(Algo):
    async def run(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        tickers = config['DEFAULT']['TICKERS'].split(',')

        async def on_trade(data):
            print("New trade:", data)

        async def on_quote(data):
            print("New quote:", data)

        self.alpaca_market_data.subscribe_stock_trades(on_trade, *tickers)
        self.alpaca_market_data.subscribe_stock_quotes(on_quote, *tickers)

        await self.alpaca_market_data.start_streams()

if __name__ == '__main__':
    algo = MyAlgo()
    asyncio.run(algo.run())
```