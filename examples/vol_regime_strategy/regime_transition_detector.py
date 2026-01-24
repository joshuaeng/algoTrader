import asyncio
from typing import Dict, Any

from src import PeriodicAgent, CommunicationBus, TradingHub, Spotter
from src.core.data_cache import DataCache
from src.data.data_types import DataObject
from queue import Queue
import math

TRANSITION_MATRIX = [
    [0.95, 0.05],  # (L->L, L->H)
    [0.30, 0.70]   # (H->L, H->H)
]

INITIAL_STATE = (1, 0)


class VolHMM:
    @staticmethod
    def gaussian_pdf(x, mu, sigma):
        return (1.0 / (sigma * math.sqrt(2 * math.pi))) * math.exp(
            -0.5 * ((x - mu) / sigma) ** 2
        )

    @staticmethod
    def high_regime_probability(
        vol_obs: float,
        prev_state_prob: list,   # [P(low), P(high)]
        transition_matrix: list, # [[P(L->L), P(L->H)], [P(H->L), P(H->H)]]
        low_params: tuple,       # (mu_L, sigma_L)
        high_params: tuple       # (mu_H, sigma_H)
    ) -> tuple:
        """
        Returns P(state = HIGH | observed vol)
        """

        # --- Prediction step (Markov transition)
        p_low_pred  = (  # P(L)
            prev_state_prob[0] * transition_matrix[0][0] +
            prev_state_prob[1] * transition_matrix[1][0]
        )

        p_high_pred = (  # P(H)
            prev_state_prob[0] * transition_matrix[0][1] +
            prev_state_prob[1] * transition_matrix[1][1]
        )

        # --- Emission likelihoods
        mu_L, sigma_L = low_params
        mu_H, sigma_H = high_params

        lik_low = VolHMM.gaussian_pdf(vol_obs, mu_L, sigma_L)  # P(V | S = L)
        lik_high = VolHMM.gaussian_pdf(vol_obs, mu_H, sigma_H)  # P(V | S = H)

        # --- Bayesian update
        unnorm_low = lik_low * p_low_pred  # P(L) x P(V | L) = P(V, L)
        unnorm_high = lik_high * p_high_pred  # # P(H) x P(V | H) = P(V, H)

        norm = unnorm_low + unnorm_high

        # posterior
        p_high_post = unnorm_high / norm
        p_low_post = 1 - p_high_post

        return p_high_post, p_low_post


class VolSnapper(PeriodicAgent):
    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        """
        The configuration dictionary should contain:
        - 'period': period between each run
        - 'snapshot_queue_size': size of the snapshot queue
        """
        super().__init__(config, data_cache, communication_bus)
        self.vols: Queue = Queue(maxsize=self.config.get('snapshot_queue_size', 100))

    def snap_spot(self, data_object: DataObject):
        self.vols.put(data_object)

    async def initialize(self):
        await self.communication_bus.subscribe_listener(f"SPOT_PRICE('VIXY')", self.snap_spot)

    async def run(self):
        self.data_cache.set('VOLS', self.vols)


class Signal(PeriodicAgent):
    def __init__(self, config: Dict[str, Any], data_cache: DataCache, communication_bus: CommunicationBus):
        super().__init__(config, data_cache, communication_bus)
        self.current_state = self.config.get("initial_state")

    @staticmethod
    def exponential_average(data, alpha: float) -> float:
        """
        Compute exponential average over a full dataset.

        Parameters
        ----------
        data : iterable of float
            Time-ordered data points.
        alpha : float
            Smoothing factor in (0,1].

        Returns
        -------
        float
            Final exponential average value.
        """
        if not data:
            raise ValueError("data must not be empty")

        if not (0 < alpha <= 1):
            raise ValueError("alpha must be in (0,1]")

        ema = data[0]  # deterministic seed
        for x in data[1:]:
            ema = alpha * x + (1 - alpha) * ema

        return ema

    def get_signal(self, new_state: tuple):
        prob_move = new_state[1] - self.current_state[1]

        if new_state[1] > 0.6 and prob_move > 0.05:
            return "HIGH VOL / UP"

        if new_state[1] > 0.6 and prob_move < -0.05:
            return "HIGH VOL / DOWN"

        if 0.6 >= new_state[1] > 0.4 and prob_move > 0.05:
            return "TRANSITION / UP"

        if 0.6 >= new_state[1] > 0.4 and prob_move < -0.05:
            return "TRANSITION / DOWN"

        if 0.4 >= new_state[1] and prob_move > 0.05:
            return "LOW VOL / UP"

        if 0.4 >= new_state[1] and prob_move < -0.05:
            return "LOW VOL / DOWN"

    async def run(self):
        vols = self.data_cache.get('SPOTS')

        if not vols:
            return

        vols: list[float] = [vol.value for vol in vols]
        exp_average = self.exponential_average(vols, alpha=0.4)

        vol_hmm = VolHMM()
        new_state = vol_hmm.high_regime_probability(
            vol_obs=exp_average,
            transition_matrix=TRANSITION_MATRIX,
            low_params=(15, 5),
            high_params=(25, 10),
            prev_state_prob=self.current_state
        )

        signal = self.get_signal(new_state)
        self.current_state = new_state

        await self.communication_bus.publish('SIGNAL', signal)


async def main():
    """Main function to set up and run the algorithm."""

    trading_hub = TradingHub(
        api_key="",
        secret_key="", paper=True
    )
    instruments = ["VIXY"]
    await trading_hub.add_agent(Spotter, {'instruments': instruments, 'throttle': '1s'})
    await trading_hub.add_agent(VolSnapper, {'period': '1s', 'snapshot_queue_size': 10})
    await trading_hub.add_agent(Signal, {'period': '1s', 'initial_state': INITIAL_STATE})
    await trading_hub.start()


if __name__ == "__main__":
    asyncio.run(main())













