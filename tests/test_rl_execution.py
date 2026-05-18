import pytest
import numpy as np
from stable_baselines3 import PPO
from src.env import HFTLimitOrderEnv

def test_ppo_outperforms_static():
    # Initialize environment
    env = HFTLimitOrderEnv()

    # Static Strategy: Always use spread 0.5
    static_rewards = []
    for _ in range(10):
        obs, _ = env.reset(seed=42)
        total_reward = 0
        done = False
        truncated = False
        while not (done or truncated):
            obs, reward, done, truncated, _ = env.step([0.5])
            total_reward += reward
        static_rewards.append(total_reward)
    mean_static_reward = np.mean(static_rewards)

    # RL Strategy: PPO Agent
    try:
        model = PPO.load("brain/execution_ppo.zip")
    except FileNotFoundError:
        pytest.fail("Trained model brain/execution_ppo.zip not found. Run training script first.")

    ppo_rewards = []
    for _ in range(10):
        obs, _ = env.reset(seed=42)
        total_reward = 0
        done = False
        truncated = False
        while not (done or truncated):
            action, _states = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, _ = env.step(action)
            total_reward += reward
        ppo_rewards.append(total_reward)
    mean_ppo_reward = np.mean(ppo_rewards)

    print(f"Mean Static Strategy Reward: {mean_static_reward}")
    print(f"Mean PPO Agent Reward: {mean_ppo_reward}")

    # Verify PPO outperforms static strategy
    assert mean_ppo_reward > mean_static_reward, f"PPO Agent ({mean_ppo_reward}) failed to outperform Static Strategy ({mean_static_reward})"
