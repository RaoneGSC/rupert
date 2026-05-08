import time
import numpy as np
from stable_baselines3 import PPO
from rupert_env import RupertEnv
from stable_baselines3.common.callbacks import CheckpointCallback

def train_agent():
    print("Starting training without GUI (DIRECT mode)...")
    env = RupertEnv(render_mode="direct")  # headless mode for speed
    model = PPO("MlpPolicy", env, verbose=1)

    # save checkpoint every 100k steps
    checkpoint_callback = CheckpointCallback(
        save_freq=100000,
        save_path="./checkpoints",
        name_prefix="rupert_policy"
    )

    model.learn(total_timesteps=1_000_000, callback=checkpoint_callback)
    model.save("ppo_rupert")
    env.close()
    print("Training complete. Model saved.")

def demo_agent():
    print("Loading model for GUI demo...")
    env = RupertEnv(render_mode="human")  # enable visualization for demo
    model = PPO.load("ppo_rupert")
    obs, _ = env.reset()
    done = False
    while not done:
        action, _states = model.predict(obs, deterministic=True)
        obs, reward, done, info, _ = env.step(action)
        time.sleep(1/100)
    env.close()
    print("Demo finished.")

def test_fixed_point(target_position):
    print(f"\n=== Testing fixed point: {target_position} ===")
    env = RupertEnv(render_mode="human")
    model = PPO.load("ppo_rupert")
    obs, _ = env.reset(options={"cube_pos": target_position})
    done = False
    while not done:
        action, _states = model.predict(obs, deterministic=True)
        obs, reward, done, info, _ = env.step(action)
        time.sleep(1/5)
    env.close()
    print("Test finished.\n")

if __name__ == "__main__":
    #train_agent()
    #demo_agent()
    test_fixed_point([-0.3, 0, 1.4])
