import serial
import keyboard
import time

porta = "COM4"  # Ajuste para sua porta
baudrate = 115200

ser = serial.Serial(porta, baudrate, timeout=0)  # timeout=0 para evitar fila

tecla_anterior = None  # Armazena última tecla pressionada
tempo_pressao = 0.2  # Tempo mínimo (em segundos) entre os comandos enquanto a tecla estiver pressionada
tempo_ultimo_comando = 0  # Armazena o tempo do último comando enviado

print("Controle iniciado! Use W, A, S, D para movimentar. ESC para sair.")

while True:
    tecla_atual = None  # Reseta a tecla atual
    tempo_atual = time.time()  # Obtém o tempo atual

    # Verifica teclas pressionadas
    if keyboard.is_pressed("w"):
        tecla_atual = "w"
    elif keyboard.is_pressed("s"):
        tecla_atual = "s"
    elif keyboard.is_pressed("a"):
        tecla_atual = "a"
    elif keyboard.is_pressed("d"):
        tecla_atual = "d"
    
    # Só envia um comando se a tecla mudou ou se a tecla foi pressionada por mais tempo que o intervalo
    if tecla_atual and (tecla_atual != tecla_anterior or tempo_atual - tempo_ultimo_comando > tempo_pressao):
        ser.write(tecla_atual.encode() + b"\n")
        print(f"Enviado: {tecla_atual}")
        tempo_ultimo_comando = tempo_atual  # Atualiza o tempo do último comando
    
    tecla_anterior = tecla_atual  # Atualiza a tecla anterior

    # Sai com ESC
    if keyboard.is_pressed("esc"):
        print("Saindo...")
        break

    time.sleep(0.05)  # Pequeno delay para suavizar a leitura

ser.close()