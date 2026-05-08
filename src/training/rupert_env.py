import numpy as np
import gymnasium as gym
from gymnasium import spaces
import pybullet as p
import pybullet_data
import time
import os

class RupertEnv(gym.Env):
    metadata = {"render_modes": ["human"], "render_fps": 60}

    def __init__(self, render_mode="direct"):
        super().__init__()
        self.render_mode = render_mode
        self.time_step = 1 / 240.0

        self.joint1_range = [-28, 28]
        self.joint2_range = [-90, 90]
        self.action_space = spaces.Box(low=-1, high=1, shape=(2,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(8,), dtype=np.float32)

        if render_mode == "human":
            self.physics_client = p.connect(p.GUI)
        else:
            self.physics_client = p.connect(p.DIRECT)

        p.setAdditionalSearchPath(pybullet_data.getDataPath())

        self.LINK1_JOINT_IDX = 0
        self.LINK2_JOINT_IDX = 1
        self.LOWER_ARM_LINK_IDX = 1

        self.max_steps = 150
        self.current_step = 0

        # Carrega posições viáveis
        if os.path.exists("reachable_points.npy"):
            self.reachable_positions = np.load("reachable_points.npy")
        else:
            raise FileNotFoundError("Arquivo 'reachable_points.npy' não encontrado.")

        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        p.resetSimulation()
        p.setGravity(0, 0, -9.8)
        p.setTimeStep(self.time_step)
        self.current_step = 0

        p.loadURDF("plane.urdf")
        start_pos = [0, 0, 0.1]
        start_ori = p.getQuaternionFromEuler([0, 0, 0])
        self.arm_id = p.loadURDF("RupertV2.urdf", start_pos, start_ori, useFixedBase=True)

        p.resetJointState(self.arm_id, self.LINK1_JOINT_IDX, targetValue=0)
        p.resetJointState(self.arm_id, self.LINK2_JOINT_IDX, targetValue=0)

        # Respeita ponto passado via options (ex: test_fixed_point)
        if options is not None and "cube_pos" in options:
            self.cube_pos = options["cube_pos"]
        else:
            self.cube_pos = self.reachable_positions[np.random.randint(len(self.reachable_positions))]

        print(f"[reset] Cubo posicionado em: {self.cube_pos}")

        cube_collision = p.createCollisionShape(p.GEOM_BOX, halfExtents=[0.05, 0.05, 0.05])
        cube_visual = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.05, 0.05, 0.05], rgbaColor=[1, 0, 0, 1])
        self.cube_id = p.createMultiBody(baseMass=0,
                                         baseCollisionShapeIndex=cube_collision,
                                         baseVisualShapeIndex=cube_visual,
                                         basePosition=self.cube_pos)

        return self._get_obs(), {}

    def step(self, action):
        self.current_step += 1
        joint1_deg = np.interp(action[0], [-1, 1], self.joint1_range)
        joint2_deg = np.interp(action[1], [-1, 1], self.joint2_range)

        joint1_rad = np.deg2rad(joint1_deg)
        joint2_rad = np.deg2rad(joint2_deg)

        p.setJointMotorControl2(self.arm_id, self.LINK1_JOINT_IDX, p.POSITION_CONTROL,
                                targetPosition=joint1_rad, force=500)
        p.setJointMotorControl2(self.arm_id, self.LINK2_JOINT_IDX, p.POSITION_CONTROL,
                                targetPosition=joint2_rad, force=500)

        for _ in range(30):
            p.stepSimulation()
            if self.render_mode == "human":
                time.sleep(self.time_step)

        obs = self._get_obs()

        closest_points = p.getClosestPoints(bodyA=self.arm_id, bodyB=self.cube_id,
                                            linkIndexA=self.LOWER_ARM_LINK_IDX, distance=10)
        if len(closest_points) > 0:
            min_dist = min([pt[8] for pt in closest_points])
        else:
            min_dist = 10

        collision = min_dist <= 0
        reward = -min_dist - 0.01
        if collision:
            reward += 20
            done = True
        elif self.current_step >= self.max_steps:
            done = True
        else:
            done = False

        return obs, reward, done, False, {}

    def _get_obs(self):
        joint1 = p.getJointState(self.arm_id, self.LINK1_JOINT_IDX)[0]
        joint2 = p.getJointState(self.arm_id, self.LINK2_JOINT_IDX)[0]
        joint1_deg = np.rad2deg(joint1)
        joint2_deg = np.rad2deg(joint2)

        lower_arm_pos = p.getLinkState(self.arm_id, self.LOWER_ARM_LINK_IDX)[0]

        return np.array([joint1_deg, joint2_deg, *lower_arm_pos, *self.cube_pos], dtype=np.float32)

    def close(self):
        p.disconnect()
