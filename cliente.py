import socket
import struct
import threading
import time
import sys
from protocol import *

HOST = '127.0.0.1'
PORT = 3000

def escutar_gerenciador(conn):
    """
    Thread dedicada a ouvir respostas e alertas do Gerenciador.
    """
    try:
        while True:
            # Aguarda o cabeçalho de 3 bytes
            header = conn.recv(3)
            if not header:
                print("\n[ERRO] Conexão com o Gerenciador foi encerrada.")
                break
                
            orig, dest, msg_id, payload_size = unpack_header(header)
            
            # Lê o payload com base no tamanho informado no cabeçalho
            bytes_to_read = (payload_size + 7) // 8 if payload_size > 0 else 0
            payload = conn.recv(bytes_to_read)
            
            if msg_id == RES_LEITURA:
                # Payload do RES_LEITURA: 1 byte (func) + 4 bytes (float)
                func_id = payload[0]
                dado = struct.unpack('!f', payload[1:5])[0]
                
                metricas = {0: "Temperatura (°C)", 1: "Batimentos Cardíacos", 2: "Umidade (%)", 3: "Oxigenação (%)"}
                metrica_nome = metricas.get(func_id, "Desconhecido")
                print(f"\n[LEITURA] {metrica_nome}: {dado:.2f}")
                print("\nDigite sua opção: ", end="", flush=True)

            elif msg_id == ALERTA:
                # Payload do ALERTA: 1 byte (flag/origem) + 4 bytes (float)
                flag = payload[0] >> 4
                origem_disp = payload[0] & 0b1111
                dado = struct.unpack('!f', payload[1:5])[0]
                
                status = "ERRO/FALHA" if flag == ERROR else "FORA DO LIMITE"
                print(f"\n[!!! ALERTA !!!] {NOMES_DISPOSITIVOS.get(origem_disp, origem_disp)} | Status: {status} | Valor Registrado: {dado:.2f}")
                print("\nDigite sua opção: ", end="", flush=True)

    except Exception as e:
        print(f"\n[ERRO] Falha na comunicação: {e}")
        sys.exit(0)

def exibir_menu():
    print("\n" + "="*30)
    print("      MENU DO CLIENTE")
    print("="*30)
    print("1. Solicitar Leitura de Temperatura")
    print("2. Solicitar Leitura de Umidade")
    print("3. Solicitar Leitura de Oxigenação")
    print("4. Solicitar Leitura de Batimentos Cardíacos")
    print("5. Alterar Configuração (Limites)")
    print("0. Sair")
    print("="*30)

def iniciar_cliente():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print("[CLIENTE] Conectando ao Gerenciador...")
        try:
            s.connect((HOST, PORT))
            req_header = pack_header(ID_CLIENTE, ID_GERENCIADOR, REQ_REGISTRO, 0)
            s.sendall(req_header)
            print("[CLIENTE] Conectado e identificado com sucesso!")
        except ConnectionRefusedError:
            print("[ERRO] Não foi possível conectar. O Gerenciador está rodando?")
            return

        # Inicia a thread para escutar mensagens assíncronas (Alertas e Leituras)
        thread_escuta = threading.Thread(target=escutar_gerenciador, args=(s,), daemon=True)
        thread_escuta.start()
        
        # Loop interativo do Menu
        while True:
            time.sleep(0.5) # Pausa breve para não atropelar a interface gráfica do console
            exibir_menu()
            opcao = input("Digite sua opção: ")
            
            if opcao == '0':
                print("[CLIENTE] Encerrando...")
                break
                
            elif opcao in ['1', '2', '3', '4']:
                # Mapeia a opção do menu para o ID do Sensor correto
                mapa_sensores = {
                    '1': ID_SENSOR_TEMP,
                    '2': ID_SENSOR_UMID,
                    '3': ID_SENSOR_OXIG,
                    '4': ID_SENSOR_BAT_CARD
                }
                id_alvo = mapa_sensores[opcao]
                
                # Payload de requisição de leitura é um int de 4 bytes ('!i')
                payload_req = struct.pack('!i', id_alvo)
                req_leitura_header = pack_header(ID_CLIENTE, ID_GERENCIADOR, REQ_LEITURA, 32)
                
                s.sendall(req_leitura_header + payload_req)
                print(f"[CLIENTE] Solicitação de leitura enviada (Sensor {id_alvo})...")
                
            elif opcao == '5':
                print("\n--- Configuração de Limites ---")
                print("0: Temperatura | 1: Batimentos | 2: Umidade | 3: Oxigenação")
                try:
                    func_id = int(input("Digite o ID da métrica que deseja configurar: "))
                    val_min = float(input("Digite o valor MÍNIMO: "))
                    val_max = float(input("Digite o valor MÁXIMO: "))
                    
                    # Payload de Config: 1 byte (func) + 4 bytes (min) + 4 bytes (max) = 9 bytes (72 bits)
                    payload_config = struct.pack('!Bff', func_id, val_min, val_max)
                    config_header = pack_header(ID_CLIENTE, ID_GERENCIADOR, CONFIG, 72)
                    
                    s.sendall(config_header + payload_config)
                    print("[CLIENTE] Nova configuração enviada ao Gerenciador.")
                except ValueError:
                    print("[ERRO] Por favor, insira valores numéricos válidos.")
                
            else:
                print("Opção inválida.")

if __name__ == "__main__":
    iniciar_cliente()