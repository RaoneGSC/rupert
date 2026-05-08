import numpy as np
import matplotlib.pyplot as plt
from rupert_env import RupertEnv
import pybullet as p

# Parâmetros da grade 3D
x_vals = np.linspace(-0.5, 0.5, 20)
y_vals = np.linspace(-0.5, 0.5, 20)
z_vals = np.linspace(0.5, 2.0, 20)

reachable_points = []

env = RupertEnv(render_mode="direct")

for x in x_vals:
    for y in y_vals:
        for z in z_vals:
            env.cube_pos = [x, y, z]
            env.reset()
            found = False

            # Teste de grades de ações determinísticas (varrendo espaço de ação)
            for joint1 in np.linspace(-1, 1, 6):
                for joint2 in np.linspace(-1, 1, 6):
                    action = np.array([joint1, joint2])
                    obs, reward, done, _, _ = env.step(action)
                    
                    if reward > 0:  # colidiu
                        reachable_points.append([x, y, z])
                        found = True
                        break
                if found:
                    break

env.close()

# Visualização dos pontos atingíveis
reachable_points = np.array(reachable_points)
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.scatter(reachable_points[:, 0], reachable_points[:, 1], reachable_points[:, 2], c='r', label='Atingíveis')
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
ax.set_title('Mapa de Alcançabilidade do Rupert')
plt.legend()
plt.show()
# Após preencher 'reachable_points'
reachable_points = np.array(reachable_points)
np.save("reachable_points.npy", reachable_points)
print(f"Salvo {len(reachable_points)} pontos em 'reachable_points.npy'")