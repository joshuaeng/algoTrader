from src.algo import Algo
from src.algos.momentum_algo import MomentumAlgo
from src.data_cache import DataCache
import configparser
import asyncio
from collections import deque


class DataCollector(Algo):
    async def run(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        tickers = config['DEFAULT']['TICKERS'].split(',')
        lookback = int(config['momentum']['lookback'])

        # Initialize the cache with empty deques for each ticker
        for ticker in tickers:
            self._put_in_cache(f"{ticker}_prices", deque(maxlen=lookback))

        async def on_trade(data):
            print("New trade:", data)
            # Get the deque from the cache
            prices = self._get_from_cache(f"{data.symbol}_prices")
            if prices is not None:
                # Append the new price to the deque
                prices.append(data.price)
                # Put the updated deque back in the cache
                self._put_in_cache(f"{data.symbol}_prices", prices)

        self.alpaca_market_data.subscribe_stock_trades(on_trade, *tickers)

        await self.alpaca_market_data.start_streams()


async def run_momentum_algo(cache: DataCache):
    momentum_algo = MomentumAlgo(cache)
    await momentum_algo.run()

if __name__ == '__main__':
    # Create a shared cache for all algorithms
    cache_ = DataCache()

    data_collector = DataCollector(cache_)
    
    loop = asyncio.get_event_loop()
    loop.create_task(data_collector.run())
    loop.create_task(run_momentum_algo(cache_))
    loop.run_forever()
