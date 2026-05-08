import serial
import time

# Ajuste para a porta serial correta do seu Pico
PORTA_SERIAL = 'COM4'  # Altere para a porta correta
BAUDRATE = 115200

# Comando para enviar (ângulo do servo 1, ângulo do servo 2)
comando = "90,120\n"

try:
    with serial.Serial(PORTA_SERIAL, BAUDRATE, timeout=2) as ser:
        print(f"Conectado à {PORTA_SERIAL}")
        time.sleep(2)  # Aguarda o Pico inicializar

        # Envia comando
        ser.write(comando.encode())
        print(f"Comando enviado: {comando.strip()}")

        # Lê respostas
        while True:
            resposta = ser.readline().decode().strip()
            if resposta:
                print(f"Resposta do Pico: {resposta}")
            else:
                break

except serial.SerialException as e:
    print(f"Erro ao abrir porta serial: {e}")
