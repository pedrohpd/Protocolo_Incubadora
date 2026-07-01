import socket
import threading
import time
import random
from protocol import *

# Configuração do Servidor do Ambiente
HOST = '127.0.0.1'
PORT_ENV = 5000  # Porta separada do Gerenciador

# Estado da incubadora
environment = {
    ID_SENSOR_TEMP: 37.0,
    ID_SENSOR_UMID: 75.0,
    ID_SENSOR_OXIG: 92.0,
    ID_SENSOR_BAT_CARD: 140.0
}

# Estado dos atuadores (0 = Desligado, 1 = Ligado)
atuadores = {
    ID_ATUADOR_AQUEC: 0,
    ID_ATUADOR_UMID: 0,
    ID_ATUADOR_CIRC_AR: 0
}

def simulate_environment():
    """
    Roda em background a cada 1 segundo. 
    Simula as leis da termodinâmica da incubadora.
    """
    while True:
        # TEMPERATURA
        # Se o aquecedor está ligado, esquenta rápido. Se não, perde calor para o quarto.
        if atuadores[ID_ATUADOR_AQUEC] == 1:
            environment[ID_SENSOR_TEMP] *= 1.01
        else:
            environment[ID_SENSOR_TEMP] *= 0.99

        # UMIDADE
        if atuadores[ID_ATUADOR_UMID] == 1:
            environment[ID_SENSOR_UMID] *= 1.01
        else:
            environment[ID_SENSOR_UMID] *= 0.99

        # OXIGENAÇÃO
        if atuadores[ID_ATUADOR_CIRC_AR] == 1:
            environment[ID_SENSOR_OXIG] *= 1.01
        else:
            environment[ID_SENSOR_OXIG] *= 0.99

        # BATIMENTOS CARDÍACOS
        # Batimentos sofrem pequenas flutuações naturais (Random Walk)
        # Se a oxigenação cair muito, os batimentos aceleram (taquicardia)
        environment[ID_SENSOR_BAT_CARD] += random.uniform(-2.0, 2.0)
        if environment[ID_SENSOR_OXIG] < 80.0:
            environment[ID_SENSOR_BAT_CARD] += 1.5 

        # Trava limites extremos para não gerar números infinitos irreais
        environment[ID_SENSOR_TEMP] = max(20.0, min(50.0, environment[ID_SENSOR_TEMP]))
        environment[ID_SENSOR_UMID] = max(0.0, min(100.0, environment[ID_SENSOR_UMID]))
        environment[ID_SENSOR_OXIG] = max(0.0, min(100.0, environment[ID_SENSOR_OXIG]))
        
        # Imprime o painel do ambiente a cada segundo
        print(f"[AMBIENTE FÍSICO] "
              f"Temp: {environment[ID_SENSOR_TEMP]:.1f}°C | "
              f"Umid: {environment[ID_SENSOR_UMID]:.1f}% | "
              f"O2: {environment[ID_SENSOR_OXIG]:.1f}% | "
              f"BPM: {environment[ID_SENSOR_BAT_CARD]:.0f}")
        
        time.sleep(1)

def server():
    """
    Servidor UDP que permite aos Sensores lerem os dados e aos Atuadores alterarem o estado.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((HOST, PORT_ENV))
        print(f"[SIMULADOR DE AMBIENTE]: Iniciando simulação")

        while True:
            try:
                data, addr = s.recvfrom(1024)
                msg = data.decode('utf-8').strip().split()

                if not msg: continue

                comm = msg[0]

                # Sensor pedindo leitura
                if comm == "GET" and len(msg) == 2:
                    id_disp = int(msg[1])
                    valor = environment.get(id_disp, 0.0)
                    s.sendto(f"{valor:.2f}".encode('utf-8'), addr)

                # Atuador alterando o ambiente
                elif comm == "SET" and len(msg) == 3:
                    id_disp = int(msg[1])
                    novo_estado = int(msg[2])
                    if id_disp in atuadores:
                        atuadores[id_disp] = novo_estado
                        str_estado = "LIGADO" if novo_estado == 1 else "DESLIGADO"
                        print(f"[{NOMES_DISPOSITIVOS.get(id_disp, id_disp)}] foi {str_estado}.")
                    s.sendto(b"OK", addr)
            except Exception as e:
                print(f"[ERRO]: {e}")

if __name__ == "__main__":
    # Inicia a thread que processa a termodinâmica
    t = threading.Thread(target=simulate_environment, daemon=True)
    t.start()
    
    # Inicia o servidor UDP na main thread
    server()