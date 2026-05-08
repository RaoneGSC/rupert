import pybullet
import pybullet_data
import time
import serial

# Configuração da comunicação serial com o Pico
porta = "COM4"  # Ajuste para sua porta
baudrate = 230400
ser = serial.Serial(porta, baudrate, timeout=0)

# Inicialização do PyBullet
physics_client = pybullet.connect(pybullet.GUI)
pybullet.resetSimulation()
pybullet.setAdditionalSearchPath(pybullet_data.getDataPath())
pybullet.setGravity(0.0, 0.0, -9.8)
time_step = 1./240.
pybullet.setTimeStep(time_step)

# Carregar plano e robô
plane_id = pybullet.loadURDF("plane.urdf")
arm_start_pos = [0, 0, 0.1]
arm_start_orientation = pybullet.getQuaternionFromEuler([0, 0, 0])
arm_id = pybullet.loadURDF("RupertV2.urdf", arm_start_pos, arm_start_orientation, useFixedBase=True)

# Índices dos joints
LINK1_JOINT_IDX = 0  # eixo horizontal
LINK2_JOINT_IDX = 1  # eixo vertical

# Variáveis de controle
delta_tempo = 0.05      # envio mais rápido
ultimo_envio = time.time()
tolerancia = 0.5         # tolerância menor para movimentos finos
suavizacao_base = 0.2    # fator base de suavização (0-1)

def sim_to_servo_angle(sim_angle_deg, eixo):
    if eixo == 1:
        servo_angle = sim_angle_deg + 90  # vertical
    elif eixo == 0:
        servo_angle = ((sim_angle_deg + 30)/ 60.0) * 180.0  # horizontal
    else:
        servo_angle = sim_angle_deg
    return max(0, min(180, servo_angle))

def enviar_comando_angulo(angulo1, angulo2):
    comando = f"{int(angulo1)},{int(angulo2)}\n"
    ser.write(comando.encode())
    ser.flush()
    print(f"Enviado: {comando.strip()}")

# Inicialização das posições
joint1_pos = pybullet.getJointState(arm_id, LINK1_JOINT_IDX)[0] * (180 / 3.1416)
joint2_pos = pybullet.getJointState(arm_id, LINK2_JOINT_IDX)[0] * (180 / 3.1416)
servo_angle1 = sim_to_servo_angle(joint1_pos, 0)
servo_angle2 = sim_to_servo_angle(joint2_pos, 1)
enviar_comando_angulo(servo_angle1, servo_angle2)
time.sleep(1)

# Loop principal
while True:
    joint1_pos_novo = pybullet.getJointState(arm_id, LINK1_JOINT_IDX)[0] * (180 / 3.1416)
    joint2_pos_novo = pybullet.getJointState(arm_id, LINK2_JOINT_IDX)[0] * (180 / 3.1416)

    servo_angle1_novo = sim_to_servo_angle(joint1_pos_novo, 0)
    servo_angle2_novo = sim_to_servo_angle(joint2_pos_novo, 1)

    # Suavização proporcional à diferença de ângulo
    delta1 = servo_angle1_novo - servo_angle1
    delta2 = servo_angle2_novo - servo_angle2

    servo_angle1_novo = servo_angle1 + delta1 * min(suavizacao_base + abs(delta1)/50.0, 1.0)
    servo_angle2_novo = servo_angle2 + delta2 * min(suavizacao_base + abs(delta2)/50.0, 1.0)

    if (abs(servo_angle1_novo - servo_angle1) > tolerancia or
        abs(servo_angle2_novo - servo_angle2) > tolerancia):

        if time.time() - ultimo_envio > delta_tempo:
            enviar_comando_angulo(servo_angle1_novo, servo_angle2_novo)
            servo_angle1 = servo_angle1_novo
            servo_angle2 = servo_angle2_novo
            ultimo_envio = time.time()

    pybullet.stepSimulation()
    time.sleep(time_step)

    if pybullet.isConnected() == 0:
        break

ser.close()
