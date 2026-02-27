import asyncio
import os
import sys
from typing import Dict, Any, List, Tuple
from queue import Queue
from dataclasses import dataclass
from loguru import logger
import math

from src import PeriodicAgent, CommunicationBus, TradingHub, Spotter
from src.core.data_cache import DataCache
from src.data.data_types import DataObject


# ==================== HMM Implementation ====================

@dataclass
class RegimeProbabilities:
    """Clear named probabilities for each regime"""
    low: float  # Probability of low volatility regime
    high: float  # Probability of high volatility regime


class VolatilityHMM:
    """
    Hidden Markov Model for detecting volatility regimes in VIXY.

    States:
        - Low volatility: mean=15%, std=5%
        - High volatility: mean=25%, std=10%

    Transitions:
        Low -> Low:   0.95  (stays in low)
        Low -> High:  0.05  (switches to high)
        High -> Low:  0.50  (switches to low)
        High -> High: 0.50  (stays in high)
    """

    LOW_MEAN = 14.0  # VIX ~14 in calm markets
    LOW_STD = 3.5  # typical range 10-18
    HIGH_MEAN = 28.0  # VIX ~28 in stressed markets
    HIGH_STD = 8.0  # wide range 20-45+

    TRANS_LOW_TO_LOW = 0.981
    TRANS_LOW_TO_HIGH = 0.019
    TRANS_HIGH_TO_LOW = 0.051
    TRANS_HIGH_TO_HIGH = 0.949

    @staticmethod
    def gaussian_pdf(x: float, mu: float, sigma: float) -> float:
        """Probability density of normal distribution"""
        return (1.0 / (sigma * math.sqrt(2 * math.pi))) * math.exp(
            -0.5 * ((x - mu) / sigma) ** 2
        )

    @classmethod
    def update_beliefs(cls,
                       observed_vol: float,
                       prior: RegimeProbabilities) -> RegimeProbabilities:
        """
        Update regime beliefs using new observation.

        Args:
            observed_vol: New volatility observation (%)
            prior: Previous probabilities P(Low), P(High)

        Returns:
            Updated probabilities P(Low|obs), P(High|obs)
        """
        # --- Step 1: Predict next state using transition matrix
        # P(Low_pred) = P(Low) * P(Low->Low) + P(High) * P(High->Low)
        p_low_pred = (
                prior.low * cls.TRANS_LOW_TO_LOW +
                prior.high * cls.TRANS_HIGH_TO_LOW
        )

        # P(High_pred) = P(Low) * P(Low->High) + P(High) * P(High->High)
        p_high_pred = (
                prior.low * cls.TRANS_LOW_TO_HIGH +
                prior.high * cls.TRANS_HIGH_TO_HIGH
        )

        # --- Step 2: Calculate likelihood of observation in each state
        # P(obs | Low)
        lik_low = cls.gaussian_pdf(observed_vol, cls.LOW_MEAN, cls.LOW_STD)

        # P(obs | High)
        lik_high = cls.gaussian_pdf(observed_vol, cls.HIGH_MEAN, cls.HIGH_STD)

        # --- Step 3: Update beliefs using Bayes rule
        # Unnormalized posteriors: P(state) * P(obs|state)
        unnorm_low = lik_low * p_low_pred
        unnorm_high = lik_high * p_high_pred

        # Normalize
        norm = unnorm_low + unnorm_high

        if norm == 0:
            # Avoid division by zero - return prior
            return prior

        p_low_post = unnorm_low / norm
        p_high_post = unnorm_high / norm

        return RegimeProbabilities(low=p_low_post, high=p_high_post)


# ==================== Agents ====================

class VolSnapper(PeriodicAgent):
    """
    Collects VIXY spot prices and stores them for the HMM.
    Runs every second and keeps a rolling window of recent prices.
    """

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        super().__init__(config, data_cache, communication_bus)
        self.queue_size = self.config.get('snapshot_queue_size', 50)
        self.price_queue: Queue = Queue(maxsize=self.queue_size)
        self.recent_prices: List[float] = []  # For easier access

    def snap_spot(self, data_object: DataObject):
        """Called whenever a new VIXY spot price arrives"""
        price = data_object.get('value')
        if price:
            self.price_queue.put(price)

    async def initialize(self):
        """Subscribe to VIXY spot prices"""
        await self.communication_bus.subscribe_listener(
            "SPOT_PRICE('VIXY')",
            self.snap_spot
        )
        logger.info("VolSnapper initialized - watching VIXY")

    async def run(self):
        """Periodically update the cache with recent prices"""
        # Drain the queue into our list
        while not self.price_queue.empty():
            try:
                price = self.price_queue.get_nowait()
                self.recent_prices.append(price)
            except:
                break

        # Keep only the most recent prices
        if len(self.recent_prices) > self.queue_size:
            self.recent_prices = self.recent_prices[-self.queue_size:]

        # Store in cache for other agents
        if self.recent_prices:
            self.data_cache.set('VIXY_PRICES', self.recent_prices.copy())
            logger.debug(f"Stored {len(self.recent_prices)} VIXY prices")


class VolatilitySignal(PeriodicAgent):
    """
    Runs HMM on VIXY prices to detect volatility regime changes.
    Publishes signals when regime probabilities shift significantly.
    """

    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        super().__init__(config, data_cache, communication_bus)

        # Start with high confidence in low regime
        self.current_beliefs = RegimeProbabilities(low=0.99, high=0.01)
        self.last_signal = None
        self.min_data_points = config.get('min_data_points', 10)

    @staticmethod
    def exponential_average(data: List[float], alpha: float) -> float:
        """Compute exponential moving average"""
        if not data:
            return 0.0

        ema = data[0]
        for x in data[1:]:
            ema = alpha * x + (1 - alpha) * ema
        return ema

    def get_signal_description(self, new_beliefs: RegimeProbabilities) -> str:
        """
        Generate human-readable signal based on probability changes.
        Uses P(High) for thresholds since that's what we care about.
        """
        p_high = new_beliefs.high
        p_high_prev = self.current_beliefs.high
        prob_change = p_high - p_high_prev

        # Direction of change
        direction = "UP" if prob_change > 0.01 else "DOWN" if prob_change < -0.01 else "STABLE"

        # Regime classification
        if p_high > 0.7:
            regime = "HIGH_VOL"
        elif p_high < 0.3:
            regime = "LOW_VOL"
        else:
            regime = "TRANSITION"

        # Only signal on significant moves
        if abs(prob_change) < 0.02:
            return None

        return f"{regime}_{direction}"

    async def run(self):
        """Periodically run HMM and publish signals"""
        # Get recent prices from cache
        prices = self.data_cache.get('VIXY_PRICES')

        if not prices or len(prices) < self.min_data_points:
            logger.debug(f"Not enough data: {len(prices) if prices else 0}/{self.min_data_points}")
            return

        # Calculate smoothed volatility (using price as proxy for VIXY level)
        # For VIXY, price IS the volatility level
        smooth_vol = self.exponential_average(prices, alpha=0.3)

        # Update HMM beliefs
        new_beliefs = VolatilityHMM.update_beliefs(
            observed_vol=smooth_vol,
            prior=self.current_beliefs
        )

        # Generate signal
        signal = self.get_signal_description(new_beliefs)

        # Publish if signal changed significantly
        if signal and signal != self.last_signal:
            logger.info(f"🔥 SIGNAL: {signal} | P(High)={new_beliefs.high:.2f} | VIXY={smooth_vol:.2f}")
            await self.communication_bus.publish('VOLATILITY_SIGNAL', signal)
            self.last_signal = signal

        # Update state
        self.current_beliefs = new_beliefs

        # Also publish probabilities for other agents
        prob_data = {
            'p_low': new_beliefs.low,
            'p_high': new_beliefs.high,
            'vixy': smooth_vol,
            'timestamp': asyncio.get_event_loop().time()
        }
        await self.communication_bus.publish('REGIME_PROBS', prob_data)


# ==================== Main ====================

async def main():
    """Set up and run the volatility regime detector"""

    api_key = os.getenv('APCA_API_KEY_ID', "here")
    secret_key = os.getenv('APCA_API_SECRET_KEY', "here")

    trading_hub = TradingHub(
        api_key=api_key,
        secret_key=secret_key,
        paper=True
    )

    # Agent 1: Get VIXY spot prices
    await trading_hub.add_agent(Spotter, {
        'instruments': ["VIXY"],
        'throttle': '1s',
        'fair_price_method': 'mid'  # Use mid price for VIXY
    })

    # Agent 2: Collect price snapshots
    await trading_hub.add_agent(VolSnapper, {
        'period': '1s',
        'snapshot_queue_size': 100  # Keep last 100 prices
    })

    # Agent 3: Run HMM and generate signals
    await trading_hub.add_agent(VolatilitySignal, {
        'period': '2s',  # Run every 2 seconds
        'min_data_points': 20  # Need 20 prices before starting
    })

    logger.info("Starting Volatility Regime Detector for VIXY")
    logger.info("Signals: HIGH_VOL_UP/DOWN, LOW_VOL_UP/DOWN, TRANSITION_UP/DOWN")

    await trading_hub.start()


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("momentum_strategy.log", rotation="5 MB", level="DEBUG", catch=False)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")