import gymnasium as gym
import numpy as np
from gymnasium import spaces

class HFTLimitOrderEnv(gym.Env):
    """
    Simulates a high-frequency trading order book environment for limit order execution.
    The agent chooses a spread distance (0 to max_spread) for limit orders.
    A tighter spread increases fill probability but reduces the captured maker fee per execution.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, max_spread=0.01, maker_fee=0.0001, volatility=0.001):
        super().__init__()

        self.max_spread = max_spread
        self.maker_fee = maker_fee
        self.volatility = volatility

        # Action space: continuous spread positioning [0, 1] scaled to [0, max_spread]
        # 0 = aggressive (tightest spread), 1 = passive (widest spread)
        self.action_space = spaces.Box(low=0, high=1, shape=(1,), dtype=np.float32)

        # Observation space: simulated market conditions (e.g., current volatility, trend)
        self.observation_space = spaces.Box(low=-1, high=1, shape=(3,), dtype=np.float32)

        self.current_step = 0
        self.max_steps = 1000

        # Internal state
        self._current_vol = self.volatility
        self._current_trend = 0.0
        self._book_imbalance = 0.0

    def _get_obs(self):
        return np.array([self._current_vol, self._current_trend, self._book_imbalance], dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0

        # Randomize initial market state
        self._current_vol = self.np_random.uniform(0.5, 1.5) * self.volatility
        self._current_trend = self.np_random.uniform(-0.05, 0.05)
        self._book_imbalance = self.np_random.uniform(-0.5, 0.5)

        return self._get_obs(), {}

    def step(self, action):
        self.current_step += 1

        # Extract spread positioning choice
        spread_choice = float(np.clip(action[0], 0, 1))
        actual_spread = spread_choice * self.max_spread

        # Simulate fill probability: wider spread -> lower probability
        # Also impacted by current volatility and book imbalance
        base_fill_prob = max(0.0, 1.0 - spread_choice)
        vol_impact = self._current_vol / self.volatility

        # Randomized probability threshold
        fill_prob = np.clip(base_fill_prob * vol_impact + self.np_random.uniform(-0.1, 0.1), 0.0, 1.0)

        is_filled = self.np_random.random() < fill_prob

        # Reward calculation: if filled, capture the spread + maker fee
        if is_filled:
            reward = actual_spread + self.maker_fee
        else:
            # Small penalty for missed execution opportunity (adverse selection)
            reward = -0.00005

        # Evolve market state
        self._current_vol = np.clip(self._current_vol + self.np_random.uniform(-0.1, 0.1) * self.volatility, 0.1*self.volatility, 3.0*self.volatility)
        self._current_trend = np.clip(self._current_trend + self.np_random.uniform(-0.01, 0.01), -0.1, 0.1)
        self._book_imbalance = np.clip(self._book_imbalance + self.np_random.uniform(-0.1, 0.1), -1.0, 1.0)

        done = self.current_step >= self.max_steps
        truncated = False

        info = {
            "is_filled": is_filled,
            "actual_spread": actual_spread,
            "fill_prob": fill_prob,
            "reward": reward
        }

        return self._get_obs(), reward, done, truncated, info

    def render(self):
        pass
