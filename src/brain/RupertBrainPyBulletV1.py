import pybullet
import pybullet_data
import time
import serial

# Serial communication setup with Pico
port = "COM4"  # adjust to your port
baudrate = 230400  # increased for better transfer rate
ser = serial.Serial(port, baudrate, timeout=0)

# PyBullet initialization
physics_client = pybullet.connect(pybullet.GUI)
pybullet.resetSimulation()
pybullet.setAdditionalSearchPath(pybullet_data.getDataPath())
pybullet.setGravity(0.0, 0.0, 0.0)
time_step = 1./240.
pybullet.setTimeStep(time_step)

# Load plane and robot
plane_id = pybullet.loadURDF("plane.urdf")
arm_start_pos = [0, 0, 0.1]
arm_start_orientation = pybullet.getQuaternionFromEuler([0, 0, 0])
arm_id = pybullet.loadURDF("simple_2d_arm.urdf", arm_start_pos, arm_start_orientation, useFixedBase=True)

# Joint indices
LINK1_JOINT_IDX = 0
LINK2_JOINT_IDX = 1

# Smoothing and frequency control variables
send_interval = 0.1       # interval between command sends
last_send = time.time()   # tracks last send time
tolerance = 1             # angle change threshold to trigger send (degrees)

def send_angle_command(angle1, angle2):
    command = f"{int(angle1)},{int(angle2)}\n"
    ser.write(command.encode())
    ser.flush()
    print(f"Sent: {command.strip()}")
    time.sleep(0.02)  # small pause to avoid serial congestion

# Initialize servos to simulation starting position
joint1_pos = pybullet.getJointState(arm_id, LINK1_JOINT_IDX)[0] * (180 / 3.1416)
joint2_pos = pybullet.getJointState(arm_id, LINK2_JOINT_IDX)[0] * (180 / 3.1416)
send_angle_command(joint1_pos, joint2_pos)
time.sleep(1)  # wait for servos to reach initial position

# Simulation loop
while True:
    joint1_pos_new = pybullet.getJointState(arm_id, LINK1_JOINT_IDX)[0] * (180 / 3.1416)
    joint2_pos_new = pybullet.getJointState(arm_id, LINK2_JOINT_IDX)[0] * (180 / 3.1416)

    if abs(joint1_pos_new - joint1_pos) > tolerance or abs(joint2_pos_new - joint2_pos) > tolerance:
        if time.time() - last_send > send_interval:
            send_angle_command(joint1_pos_new, joint2_pos_new)
            joint1_pos = joint1_pos_new
            joint2_pos = joint2_pos_new
            last_send = time.time()

    pybullet.stepSimulation()
    time.sleep(time_step)

    if pybullet.isConnected() == 0:
        break

ser.close()
