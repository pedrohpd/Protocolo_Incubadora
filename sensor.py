import socket
import time
import struct
import random
import threading
from protocol import *

HOST = '127.0.0.1'
PORT = 3000

def iniciar_sensor(id):
    retry = True
    sensorType = ""
    if id == ID_SENSOR_TEMP:
        sensorType = "Temperatura"
    elif id == ID_SENSOR_OXIG:
        sensorType = "Oxigenação"
    elif id == ID_SENSOR_UMID:
        sensorType = "Umidade"
    elif id == ID_SENSOR_BAT_CARD:
        sensorType = "Batimentos Cardíacos"
    while retry:    
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print(f"Sensor de {sensorType}: Conectando ao Gerenciador...")
            s.settimeout(2.0)

            try:
                s.connect((HOST, PORT))
                # Envia REQ_REGISTRO
                req_header = pack_header(id, ID_GERENCIADOR, REQ_REGISTRO, 0)
                s.sendall(req_header)
                print(f"Sensor de {sensorType} enviou: REQ_REGISTRO")
                
                # Aguarda ACK_REGISTRO
                ack_header_bytes = s.recv(3)
                if not ack_header_bytes:
                    print(f"Sensor de {sensorType} Erro: O Gerenciador fechou a conexão inesperadamente. Outra tentativa de conexão será realizada...")
                    continue
                
                _, destino, msg_id, payload_size = unpack_header(ack_header_bytes)
                # Leitura do payload
                payload = b''
                bytes_to_read = (payload_size + 7) // 8 if payload_size > 0 else 0
                payload = s.recv(bytes_to_read)

                if destino != id:
                    print(f"[AVISO] Mensagem descartada! Destino ({destino}) não corresponde ao Sensor de {sensorType}.")
                    continue # Volta para o início do loop (ignora a mensagem)

                if msg_id == ACK_REGISTRO:
                    status = int.from_bytes(payload, byteorder='big')
                    if status == 0:
                        print(f"Sensor de {sensorType} recebeu: ACK_REGISTRO (OK). Iniciando monitoramento...")
                        
                        # Loop de monitoramento
                        while True:
                            data = 0
                            if id == ID_SENSOR_TEMP:
                                data = random.uniform(32.0, 40.0) # Intervalo ideal de temperatura (34,5 - 37,5)
                            elif id == ID_SENSOR_OXIG:
                                data = random.uniform(80.0, 100.0) # Intervalo ideal de oxigenação (90 - 100)
                            elif id == ID_SENSOR_UMID:
                                data = random.uniform(30.0, 90.0) # Intervalo ideal de umidade (40 - 80)
                            elif id == ID_SENSOR_BAT_CARD:
                                data = random.uniform(1.33, 3.0) # Intervalo ideal de batimentos cardiacos por segundo (1,66 - 2,66)

                            payload_float = struct.pack('!f', data)
                            
                            # Header: 32 bits de payload para o float
                            envio_header = pack_header(id, ID_GERENCIADOR, ENVIO_DADOS, 32)
                            s.sendall(envio_header + payload_float)
                            
                            print(f"Sensor de {sensorType}: Dados coletados = {data:.2f}")
                            time.sleep(1) # Envio a cada 1 segundo
                    else:
                        print(f"Sensor de {sensorType} recebeu: ACK_REGISTRO (ERROR). O sensor será desligado.")
                        retry = False
                        # Conexão socket será encerrada automaticamente

            except (socket.timeout, ConnectionRefusedError, ConnectionResetError, BrokenPipeError) as e: 
                print(f"Sensor de {sensorType}: Timeout de Conexão com o Gerenciador.")
                time.sleep(2)

if __name__ == "__main__":
    t1 = threading.Thread(target=iniciar_sensor, args=(ID_SENSOR_TEMP,))
    t2 = threading.Thread(target=iniciar_sensor, args=(ID_SENSOR_UMID,))
    t3 = threading.Thread(target=iniciar_sensor, args=(ID_SENSOR_OXIG,))
    t4 = threading.Thread(target=iniciar_sensor, args=(ID_SENSOR_BAT_CARD,))
    
    # Inicia threads
    t1.start()
    t2.start()
    t3.start()
    t4.start()
    
    # Impede encerramento do programa
    t1.join()
    t2.join()
    t3.join()
    t4.join()