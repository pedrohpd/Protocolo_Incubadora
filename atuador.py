import socket
import time
import struct
import threading
from protocol import *

HOST = '127.0.0.1'
PORT = 3000

def iniciar_atuador(id):
    retry = True
    atuadorType = ""
    if id == ID_ATUADOR_AQUEC:
        atuadorType = "Aquecimento"
    elif id == ID_ATUADOR_CIRC_AR:
        atuadorType = "Circulação do Ar"
    elif id == ID_ATUADOR_UMID:
        atuadorType = "Umidade"
    
    while retry:    
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print(f"Atuador de {atuadorType}: Conectando ao Gerenciador...")
            s.settimeout(2.0)

            try:
                s.connect((HOST, PORT))
                # Envia REQ_REGISTRO
                req_header = pack_header(id, ID_GERENCIADOR, REQ_REGISTRO, 0)
                s.sendall(req_header)
                print(f"Atuador de {atuadorType} enviou: REQ_REGISTRO")
                
                while True:
                    # Aguarda ACK_REGISTRO
                    ack_header_bytes = s.recv(3)
                    if not ack_header_bytes:
                        print(f"Atuador de {atuadorType} Erro: O Gerenciador fechou a conexão inesperadamente. Outra tentativa de conexão será realizada...")
                        break
                    
                    _, destino, msg_id, payload_size = unpack_header(ack_header_bytes)
                    bytes_to_read = (payload_size + 7) // 8 if payload_size > 0 else 0
                    if destino != id:
                        print(f"[AVISO] Mensagem descartada! Destino ({NOMES_DISPOSITIVOS.get(destino, destino)}) não corresponde a {NOMES_DISPOSITIVOS.get(id, id)}.")
                        continue # Volta para o início do loop (ignora a mensagem)

                    if msg_id == ACK_REGISTRO:
                        status_bytes = s.recv(bytes_to_read)
                        status = int.from_bytes(status_bytes, byteorder='big')
                        if status == 0:
                            print(f"Atuador de {atuadorType} recebeu: ACK_REGISTRO (OK). Iniciando monitoramento...")
                            s.settimeout(None)            
                        else:
                            print(f"Atuador de {atuadorType} recebeu: ACK_REGISTRO (ERROR). O Atuador será desligado.")
                            retry = False
                            # Conexão socket será encerrada automaticamente
                            break
                    
                    elif msg_id == CMD_ATUADOR:
                        action_bytes = s.recv(bytes_to_read)
                        action = int.from_bytes(action_bytes, byteorder='big')
                        if action == 1:
                            print(f"Atuador de {atuadorType} recebeu: CMD_ATUADOR (LIGAR).")
                        elif action == 0:
                            print(f"Atuador de {atuadorType} recebeu: CMD_ATUADOR (DESLIGAR).")

                        # Realiza a ação
                        alter_environment(id, action)

                        # Envia o ACK_CMD para o gerenciador
                        ack_header = pack_header(id, ID_GERENCIADOR, ACK_CMD, 8)
                        s.sendall(ack_header + OK.to_bytes(1, 'big'))
                        print(f"Atuador de {atuadorType} enviou: ACK_CMD (OK)")

            except (socket.timeout, ConnectionRefusedError): 
                print(f"Atuador de {atuadorType}: Timeout de Conexão com o Gerenciador.")

def alter_environment(ID, action):
    '''
    Conexão via UDP com o simulador de ambiente para modificação das métricas
    '''
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(1.0)
        s.sendto(f'SET {ID} {action}'.encode(), ('127.0.0.1', 5000))

if __name__ == "__main__":
    t1 = threading.Thread(target=iniciar_atuador, args=(ID_ATUADOR_AQUEC,))
    t2 = threading.Thread(target=iniciar_atuador, args=(ID_ATUADOR_CIRC_AR,))
    t3 = threading.Thread(target=iniciar_atuador, args=(ID_ATUADOR_UMID,))
    
    # Inicia threads
    t1.start()
    t2.start()
    t3.start()
    
    # Impede encerramento do programa
    t1.join()
    t2.join()
    t3.join()