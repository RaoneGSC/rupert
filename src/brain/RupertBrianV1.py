import pybullet
import pybullet_data
import time
import serial

# Configuração da comunicação serial com o Pico
porta = "COM4"  # Ajuste para sua porta
baudrate = 230400  # Aumentei para melhorar a taxa de transferência
ser = serial.Serial(porta, baudrate, timeout=0)

# Inicialização do PyBullet
physics_client = pybullet.connect(pybullet.GUI)
pybullet.resetSimulation()
pybullet.setAdditionalSearchPath(pybullet_data.getDataPath())
pybullet.setGravity(0.0, 0.0, 0.0)
time_step = 1./240.
pybullet.setTimeStep(time_step)

# Carregar o plano e o robô
plane_id = pybullet.loadURDF("plane.urdf")
arm_start_pos = [0, 0, 0.1]
arm_start_orientation = pybullet.getQuaternionFromEuler([0, 0, 0])
arm_id = pybullet.loadURDF("simple_2d_arm.urdf", arm_start_pos, arm_start_orientation, useFixedBase=True)

# Índices dos joints
LINK1_JOINT_IDX = 0
LINK2_JOINT_IDX = 1

# Variáveis para suavização e controle de frequências
delta_tempo = 0.1  # Intervalo entre envios de comandos
ultimo_envio = time.time()  # Controla o tempo de envio dos comandos
tolerancia = 1  # Tolerância para enviar o comando (em graus)

# Função para enviar os ângulos via serial
def enviar_comando_angulo(angulo1, angulo2):
    comando = f"{int(angulo1)},{int(angulo2)}\n"
    ser.write(comando.encode())
    ser.flush()  # Garante envio imediato
    print(f"Enviado: {comando.strip()}")
    time.sleep(0.02)  # Pequena pausa para evitar congestionamento na serial

# Inicialização dos servos para a posição inicial da simulação
joint1_pos = pybullet.getJointState(arm_id, LINK1_JOINT_IDX)[0] * (180 / 3.1416)
joint2_pos = pybullet.getJointState(arm_id, LINK2_JOINT_IDX)[0] * (180 / 3.1416)
enviar_comando_angulo(joint1_pos, joint2_pos)
time.sleep(1)  # Pequena pausa para garantir que os servos ajustem

# Loop de simulação
while True:
    # Obter posições atuais dos joints
    joint1_pos_novo = pybullet.getJointState(arm_id, LINK1_JOINT_IDX)[0] * (180 / 3.1416)
    joint2_pos_novo = pybullet.getJointState(arm_id, LINK2_JOINT_IDX)[0] * (180 / 3.1416)

    # Verificar se houve uma mudança significativa nos ângulos
    if abs(joint1_pos_novo - joint1_pos) > tolerancia or abs(joint2_pos_novo - joint2_pos) > tolerancia:
        # Se passou tempo suficiente e há alteração significativa, enviar comando
        if time.time() - ultimo_envio > delta_tempo:
            enviar_comando_angulo(joint1_pos_novo, joint2_pos_novo)
            joint1_pos = joint1_pos_novo
            joint2_pos = joint2_pos_novo
            ultimo_envio = time.time()

    # Avançar a simulação
    pybullet.stepSimulation()
    time.sleep(time_step)

    # Verificar saída
    if pybullet.isConnected() == 0:
        break  # Fechar a conexão serial
ser.close()
 