import pybullet
import pybullet_data
import time
import math

# Conectar ao cliente gráfico do PyBullet
physics_client = pybullet.connect(pybullet.GUI) 
pybullet.resetSimulation()  # Resetar o espaço de simulação
pybullet.setAdditionalSearchPath(pybullet_data.getDataPath())  # Adicionar caminho de dados necessários para o PyBullet
pybullet.setGravity(0.0, 0.0, -9.8)  # Definir gravidade como na Terra
time_step = 1./240.
pybullet.setTimeStep(time_step)  # Definir o tempo decorrido por passo

# Carregar o plano
plane_id = pybullet.loadURDF("plane.urdf")

# Configurar a câmera
camera_distance = 2.0
camera_yaw = 0.0  # Ângulo de rotação em torno do eixo Y (em graus)
camera_pitch = -20  # Inclinação da câmera
camera_target_position = [0.0, 0.0, 0.0]
pybullet.resetDebugVisualizerCamera(camera_distance, camera_yaw, camera_pitch, camera_target_position)

# Carregar o robô
arm_start_pos = [0, 0, 0.1]  # Definir a posição inicial (x, y, z)
arm_start_orientation = pybullet.getQuaternionFromEuler([0, 0, 0])  # Definir a orientação inicial (roll, pitch, yaw)
arm_id = pybullet.loadURDF("simple_2d_arm.urdf", arm_start_pos, arm_start_orientation, useFixedBase=True)  # Impedir que o robô caia

# Configurar a câmera para a posição final
camera_distance = 1.5
camera_yaw = 180.0  # Ângulo de rotação em torno do eixo Y (em graus)
camera_pitch = -10  # Inclinação da câmera
camera_target_position = [0.0, 0.0, 1.0]
pybullet.resetDebugVisualizerCamera(camera_distance, camera_yaw, camera_pitch, camera_target_position)

# Indices dos joints do robô
LINK1_JOINT_IDX = 0
LINK2_JOINT_IDX = 1

# Adicionar parâmetros interativos
joint1_angle_param = pybullet.addUserDebugParameter("Joint1 Angle", -180, 180, 90)
joint2_angle_param = pybullet.addUserDebugParameter("Joint2 Angle", -180, 180, 90)
joint1_velocity_param = pybullet.addUserDebugParameter("Joint1 Velocity", -10, 10, 2)
joint2_velocity_param = pybullet.addUserDebugParameter("Joint2 Velocity", -10, 10, 2)
joint1_torque_param = pybullet.addUserDebugParameter("Joint1 Torque", 0, 100, 50)
joint2_torque_param = pybullet.addUserDebugParameter("Joint2 Torque", 0, 100, 50)

# Loop de simulação
while True:
    # Obter os valores dos parâmetros
    joint1_angle = pybullet.readUserDebugParameter(joint1_angle_param)
    joint2_angle = pybullet.readUserDebugParameter(joint2_angle_param)
    joint1_velocity = pybullet.readUserDebugParameter(joint1_velocity_param)
    joint2_velocity = pybullet.readUserDebugParameter(joint2_velocity_param)
    joint1_torque = pybullet.readUserDebugParameter(joint1_torque_param)
    joint2_torque = pybullet.readUserDebugParameter(joint2_torque_param)

    # Converter os ângulos para radianos
    joint1_rad = math.radians(joint1_angle)
    joint2_rad = math.radians(joint2_angle)

    # Definir o controle de posição, velocidade e torque
    pybullet.setJointMotorControl2(arm_id, LINK1_JOINT_IDX, pybullet.POSITION_CONTROL, targetPosition=joint1_rad)
    pybullet.setJointMotorControl2(arm_id, LINK2_JOINT_IDX, pybullet.POSITION_CONTROL, targetPosition=joint2_rad)
    
    pybullet.setJointMotorControl2(arm_id, LINK1_JOINT_IDX, pybullet.VELOCITY_CONTROL, targetVelocity=joint1_velocity)
    pybullet.setJointMotorControl2(arm_id, LINK2_JOINT_IDX, pybullet.VELOCITY_CONTROL, targetVelocity=joint2_velocity)

    pybullet.setJointMotorControl2(arm_id, LINK1_JOINT_IDX, pybullet.TORQUE_CONTROL, force=joint1_torque)
    pybullet.setJointMotorControl2(arm_id, LINK2_JOINT_IDX, pybullet.TORQUE_CONTROL, force=joint2_torque)

    # Avançar a simulação
    pybullet.stepSimulation()
    time.sleep(time_step)
