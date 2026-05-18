import os
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.monitor import Monitor

from src.env import HFTLimitOrderEnv

def train_ppo():
    # Ensure directories exist
    os.makedirs("brain", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Create and monitor the environment
    env = Monitor(HFTLimitOrderEnv())

    # Initialize PPO agent
    model = PPO("MlpPolicy", env, verbose=1, learning_rate=3e-4, n_steps=2048, batch_size=64)

    # Train the agent for 100,000 steps
    print("Starting training for 100,000 steps...")
    model.learn(total_timesteps=100_000)

    # Save the model
    model_path = "brain/execution_ppo.zip"
    model.save(model_path)
    print(f"Model saved to {model_path}")

    # Evaluate the trained agent
    print("Evaluating trained model...")
    eval_env = Monitor(HFTLimitOrderEnv())
    mean_reward, std_reward = evaluate_policy(model, eval_env, n_eval_episodes=10, deterministic=True)

    # Log success metrics
    log_path = "logs/rl_eval.txt"
    with open(log_path, "w") as f:
        f.write(f"PPO Agent Evaluation Metrics\n")
        f.write(f"----------------------------\n")
        f.write(f"Mean Reward: {mean_reward:.4f} +/- {std_reward:.4f}\n")
    print(f"Evaluation metrics saved to {log_path}")

if __name__ == "__main__":
    train_ppo()
