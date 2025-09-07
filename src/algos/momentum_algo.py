from src.algo import Algo
from src.data_cache import DataCache
import asyncio
import configparser
import numpy as np

class MomentumAlgo(Algo):
    def __init__(self, cache: DataCache):
        super().__init__(cache)
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.tickers = config['DEFAULT']['TICKERS'].split(',')
        self.lookback = int(config['momentum']['lookback'])
        self.rebalance_interval = int(config['momentum']['rebalance_interval'])
        self.top_n = int(config['momentum']['top_n'])

    async def run(self):
        while True:
            await asyncio.sleep(self.rebalance_interval)

            # Calculate momentum for each ticker
            momentum = {}
            for ticker in self.tickers:
                prices = self._get_from_cache(f"{ticker}_prices")
                if prices and len(prices) == self.lookback:
                    # Calculate the percentage change between the first and last price
                    momentum[ticker] = (prices[-1] - prices[0]) / prices[0]

            if not momentum:
                print("Not enough data to calculate momentum.")
                continue

            # Rank the tickers by momentum
            ranked_tickers = sorted(momentum.items(), key=lambda item: item[1], reverse=True)

            # Select the top N tickers
            top_tickers = [ticker for ticker, momentum in ranked_tickers[:self.top_n]]

            # Get the current portfolio
            positions = self.alpaca_trading.get_all_positions()
            
            # Determine which stocks to sell
            to_sell = []
            for position in positions:
                if position.symbol not in top_tickers:
                    to_sell.append(position.symbol)
            
            # Sell the stocks that are no longer in the top N
            for ticker in to_sell:
                self.alpaca_trading.submit_market_order(ticker, 1, "sell") # sell all shares

            # Determine which stocks to buy
            to_buy = []
            for ticker in top_tickers:
                if ticker not in [p.symbol for p in positions]:
                    to_buy.append(ticker)

            # Buy the new top N stocks
            if to_buy:
                # Calculate the cash available
                account = self.alpaca_trading.get_account()
                cash = float(account.cash)
                
                # Allocate capital equally among the new stocks
                capital_per_stock = cash / len(to_buy)
                
                for ticker in to_buy:
                    # Get the latest price
                    latest_price = self._get_from_cache(f"{ticker}_prices")[-1]
                    # Calculate the quantity to buy
                    qty = capital_per_stock // latest_price
                    if qty > 0:
                        self.alpaca_trading.submit_market_order(ticker, qty, "buy")
