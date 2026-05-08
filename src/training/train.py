import time
import numpy as np
from stable_baselines3 import PPO
from rupert_env import RupertEnv
from stable_baselines3.common.callbacks import CheckpointCallback

def train_agent():
    print("Iniciando treinamento sem GUI (modo DIRECT)...")
    env = RupertEnv(render_mode="direct")  # Modo sem renderização para velocidade
    model = PPO("MlpPolicy", env, verbose=1)

    # Callback para salvar checkpoints a cada 100k passos
    checkpoint_callback = CheckpointCallback(
        save_freq=100000,
        save_path="./checkpoints",
        name_prefix="rupert_policy"
    )

    model.learn(total_timesteps=1_000_000, callback=checkpoint_callback)
    model.save("ppo_rupert")
    env.close()
    print("Treinamento finalizado e modelo salvo.")

def demo_agent():
    print("Carregando modelo para demonstração com GUI...")
    env = RupertEnv(render_mode="human")  # Ativa visualização para a demo
    model = PPO.load("ppo_rupert")
    obs, _ = env.reset()
    done = False
    while not done:
        action, _states = model.predict(obs, deterministic=True)
        obs, reward, done, info, _ = env.step(action)
        time.sleep(1/100)  # Simula a ~30 FPS
    env.close()
    print("Demonstração finalizada.")

def test_fixed_point(target_position):
    print(f"\n=== Testando ponto fixo: {target_position} ===")
    env = RupertEnv(render_mode="human")
    model = PPO.load("ppo_rupert")
    obs, _ = env.reset(options={"cube_pos": target_position})
    done = False
    while not done:
        action, _states = model.predict(obs, deterministic=True)
        obs, reward, done, info, _ = env.step(action)
        time.sleep(1/5)
    env.close()
    print("Teste finalizado.\n")

if __name__ == "__main__":
    #train_agent()
    #demo_agent()
    # Teste manual em ponto fixo
    test_fixed_point([-0.3, 0, 1.4])  
# This script trains a reinforcement learning agent using the PPO algorithm on the Rupert robot environment.