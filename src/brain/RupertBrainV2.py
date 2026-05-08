import pybullet
import pybullet_data
import time
import serial

# Serial communication setup with Pico
port = "COM4"  # adjust to your port
baudrate = 230400
ser = serial.Serial(port, baudrate, timeout=0)

# PyBullet initialization
physics_client = pybullet.connect(pybullet.GUI)
pybullet.resetSimulation()
pybullet.setAdditionalSearchPath(pybullet_data.getDataPath())
pybullet.setGravity(0.0, 0.0, -9.8)
time_step = 1./240.
pybullet.setTimeStep(time_step)

# Load plane and robot
plane_id = pybullet.loadURDF("plane.urdf")
arm_start_pos = [0, 0, 0.1]
arm_start_orientation = pybullet.getQuaternionFromEuler([0, 0, 0])
arm_id = pybullet.loadURDF("RupertV2.urdf", arm_start_pos, arm_start_orientation, useFixedBase=True)

# Joint indices
LINK1_JOINT_IDX = 0  # horizontal axis
LINK2_JOINT_IDX = 1  # vertical axis

# Control variables
send_interval = 0.05      # faster sending
last_send = time.time()
tolerance = 0.5           # smaller tolerance for fine movements
smoothing = 0.2           # base smoothing factor (0-1)

def sim_to_servo_angle(sim_angle_deg, axis):
    if axis == 1:
        servo_angle = sim_angle_deg + 90  # vertical
    elif axis == 0:
        servo_angle = ((sim_angle_deg + 30) / 60.0) * 180.0  # horizontal
    else:
        servo_angle = sim_angle_deg
    return max(0, min(180, servo_angle))

def send_angle_command(angle1, angle2):
    command = f"{int(angle1)},{int(angle2)}\n"
    ser.write(command.encode())
    ser.flush()
    print(f"Sent: {command.strip()}")

# Initialize positions
joint1_pos = pybullet.getJointState(arm_id, LINK1_JOINT_IDX)[0] * (180 / 3.1416)
joint2_pos = pybullet.getJointState(arm_id, LINK2_JOINT_IDX)[0] * (180 / 3.1416)
servo_angle1 = sim_to_servo_angle(joint1_pos, 0)
servo_angle2 = sim_to_servo_angle(joint2_pos, 1)
send_angle_command(servo_angle1, servo_angle2)
time.sleep(1)

# Main loop
while True:
    joint1_pos_new = pybullet.getJointState(arm_id, LINK1_JOINT_IDX)[0] * (180 / 3.1416)
    joint2_pos_new = pybullet.getJointState(arm_id, LINK2_JOINT_IDX)[0] * (180 / 3.1416)

    servo_angle1_new = sim_to_servo_angle(joint1_pos_new, 0)
    servo_angle2_new = sim_to_servo_angle(joint2_pos_new, 1)

    # smoothing proportional to angle difference
    delta1 = servo_angle1_new - servo_angle1
    delta2 = servo_angle2_new - servo_angle2

    servo_angle1_new = servo_angle1 + delta1 * min(smoothing + abs(delta1)/50.0, 1.0)
    servo_angle2_new = servo_angle2 + delta2 * min(smoothing + abs(delta2)/50.0, 1.0)

    if (abs(servo_angle1_new - servo_angle1) > tolerance or
        abs(servo_angle2_new - servo_angle2) > tolerance):

        if time.time() - last_send > send_interval:
            send_angle_command(servo_angle1_new, servo_angle2_new)
            servo_angle1 = servo_angle1_new
            servo_angle2 = servo_angle2_new
            last_send = time.time()

    pybullet.stepSimulation()
    time.sleep(time_step)

    if pybullet.isConnected() == 0:
        break

ser.close()
