from protocol import *
import socket
import threading
import struct

HOST = '127.0.0.1'
PORT = 3000
# Última leitura de dados realizada
TEMP = -1
O2 = -1
UMID = -1
BAT = -1

# Valores default
MIN_TEMP = 35
MAX_TEMP = 38
MIN_UMID = 60
MAX_UMID = 90
MIN_O2 = 80
MAX_O2 = 95
MIN_BAT = 120
MAX_BAT = 160

# Conexões ativas
connections = {}

# Rastreamento de estado dos Atuadores entre requisitados e reconhecidos
atuadores_ack = {ID_ATUADOR_AQUEC: 0, ID_ATUADOR_UMID: 0, ID_ATUADOR_CIRC_AR: 0}
atuadores_req = {ID_ATUADOR_AQUEC: 0, ID_ATUADOR_UMID: 0, ID_ATUADOR_CIRC_AR: 0}

# Contadores para os Timeouts e Retries
atuadores_timeout_count = {ID_ATUADOR_AQUEC: 0, ID_ATUADOR_UMID: 0, ID_ATUADOR_CIRC_AR: 0}
atuadores_error_count = {ID_ATUADOR_AQUEC: 0, ID_ATUADOR_UMID: 0, ID_ATUADOR_CIRC_AR: 0}

def msg_ACK_REGISTRO(orig, status=OK):
    '''
    Cria uma mensagem ACK_REGISTRO
    '''
    header = pack_header(ID_GERENCIADOR, orig, ACK_REGISTRO, 8)
    payload = status.to_bytes(1, 'big')
    return header + payload

def msg_CMD_ATUADOR(dest, acao):
    '''
    Cria uma mensagem CMD_ATUADOR
    '''
    header = pack_header(ID_GERENCIADOR, dest, CMD_ATUADOR, 8)
    payload = acao.to_bytes(1, byteorder='big')
    return header + payload


def msg_RES_LEITURA(ID):
    '''
    Cria uma mensagem RES_LEITURA
    '''
    data = None
    func = None
    if ID == ID_SENSOR_BAT_CARD:
        data = BAT
        func = 1
    elif ID == ID_SENSOR_OXIG:
        data = O2
        func = 3
    elif ID == ID_SENSOR_TEMP:
        data = TEMP
        func = 0
    elif ID == ID_SENSOR_UMID:
        data = UMID
        func = 2
    else: return None

    header = pack_header(ID_GERENCIADOR, ID_CLIENTE, RES_LEITURA, 64)
    payload_func = func.to_bytes(1, 'big')
    payload_data = struct.pack('!f', data) # '!f' converte o float para 4 bytes
    return header + payload_func + payload_data

def msg_ALERTA(orig, flag=OK, data=0):
    '''
    Cria uma mensagem de ALERTA
    '''
    header = pack_header(ID_GERENCIADOR, ID_CLIENTE, ALERTA, 64)
    # O primeiro byte agrupa: [3 bits de padding vazio] + [1 bit FLAG] + [4 bits ID_DISPOSITIVO]
    primeiro_byte = (flag << 4) | (orig & 0b1111)
    payload_inicio = primeiro_byte.to_bytes(1, byteorder='big')
    payload_float = struct.pack('!f', data)

    return header + payload_inicio + payload_float

def send_ALERTA(orig, data=0, flag = OK):
    """
    Envia o alerta diretamente para o socket do Cliente único, se ele estiver online.
    """
    # Verifica conexão com o cliente
    if ID_CLIENTE in connections:
        conn_cliente = connections[ID_CLIENTE]
        try:
            mensagem = msg_ALERTA(orig, flag, data)
            conn_cliente.sendall(mensagem)
            print(f"[GERENCIADOR] ALERTA enviado ao Cliente único (ID {ID_CLIENTE}).")
            
        except Exception as e:
            print(f"[ERRO] Falha ao enviar alerta para o Cliente: {e}")
            
    else:
        print(f"[AVISO] Alerta de emergência gerado (Disp: {orig}), mas o Cliente está OFFLINE!")

def send_CMD_ATUADOR(atuador, on):
    '''
    Envia uma mensagem CMD_ATUADOR para o atuador desejado
    '''
    if atuador in connections:
        conn_atuador = connections[atuador]
        conn_atuador.sendall(msg_CMD_ATUADOR(atuador, on))
        estado_str = "LIGAR" if on == 1 else "DESLIGAR"
        print(f"[GERENCIADOR] ENVIADO: CMD {estado_str} para Atuador {atuador}.")
    else: # Atuador desconectado
        send_ALERTA(orig=atuador, flag=ERROR)

def process_atuador_cmd(id_atuador, on):
    """
    Lógica centralizada: aciona, aguarda o ACK e contabiliza os 3s de timeout
    """
    # Se o atuador já falhou (passou de 3 timeouts), nós o consideramos INOPERANTE
    # O 'return' impede o envio de novos comandos e o spam de alertas.
    if atuadores_timeout_count[id_atuador] > 3:
        return
    # Só fazemos algo se o Atuador ainda não confirmou que está no estado que desejamos
    if atuadores_ack[id_atuador] != on:
        if atuadores_req[id_atuador] != on:
            # Nova mudança de estado detectada
            atuadores_req[id_atuador] = on
            atuadores_timeout_count[id_atuador] = 1 # Conta 1 segundo
            atuadores_error_count[id_atuador] = 0
            send_CMD_ATUADOR(id_atuador, on)
        else:
            # RETRANSMISSÃO: ACK_CMD(OK) não foi recebido
            atuadores_timeout_count[id_atuador] += 1
            # 3 ciclos (3s) sem ACK
            if atuadores_timeout_count[id_atuador] == 4:
                print(f"[GERENCIADOR] Timeout: Atuador {id_atuador} inoperante (sem ACK em 3s).")
                send_ALERTA(orig=id_atuador, flag=ERROR)
            else:
                print(f"[GERENCIADOR] Retransmitindo CMD para Atuador {id_atuador} (Timeout).")
                send_CMD_ATUADOR(id_atuador, on)

def connection(conn, addr):
    '''
    Estabelece a comunicação entre o gerenciador e os sensores/atuadores/clientes
    '''
    global TEMP, O2, UMID, BAT
    print(f"[GERENCIADOR] Nova conexão de {addr}")
    # Variável de estado do dispositivo conectado para o envio da mensagem de alerta caso
    # a conexão seja interrompida
    ID_disp = None
    try:
        while True:
            # Leitura bloqueante com timeout
            try:
                header = conn.recv(3)
        
                # Header vazio: comunicação falhou
                if not header:
                    print(f"[GERENCIADOR] Conexão com {addr} perdida.")
                    if ID_disp != None:
                        msg_ALERTA(ID_disp, ERROR)
                    break

                orig, dest, ID_msg, payload_size = unpack_header(header)

                # Pacote com outro destino 
                # Realiza a leitura, mas ignora o conteúdo
                if dest != ID_GERENCIADOR:
                    if payload_size > 0:
                        bytes_to_read = (payload_size + 7) // 8 if payload_size > 0 else 0
                        conn.recv(bytes_to_read)
                    continue
                
                if ID_disp is None:
                    ID_disp = orig
                    connections[ID_disp] = conn

                # Leitura do payload
                payload = b''
                if payload_size > 0:
                    # Conversão para bytes
                    bytes_to_read = payload_size // 8 if payload_size >= 8 else 1
                    payload = conn.recv(bytes_to_read)

            except socket.timeout:
                break

            # Interpretação da mensagem
            if ID_msg == REQ_REGISTRO:
                print(f"[GERENCIADOR] RECEBIDO: REQ_REGISTRO do ID {orig}")
                conn.sendall(msg_ACK_REGISTRO(orig, OK))
                print(f"[GERENCIADOR] ENVIADO: ACK_REGISTRO para ID {orig}")

                # Se um Atuador inoperante for reiniciado e 
                # se reconectar, zeramos os erros para que ele volte a funcionar
                if orig in atuadores_timeout_count:
                    atuadores_timeout_count[orig] = 0
                    atuadores_error_count[orig] = 0
                    atuadores_ack[orig] = 0
                    atuadores_req[orig] = 0

                # Inicia a contagem de 5 segundos de inatividade 
                conn.settimeout(5.0)
            
            elif ID_msg == ENVIO_DADOS:
                print(f"[GERENCIADOR] RECEBIDO: ENVIO_DADOS do Sensor {orig} -> Valor: {data:.2f}")
                data = struct.unpack('!f', payload)[0]

                # Envia ALERTA e aciona os Atuadores caso a leitura esteja fora dos limites
                if orig == ID_SENSOR_BAT_CARD:
                    BAT = data
                    if data > MAX_BAT or data < MIN_BAT:
                        send_ALERTA(orig, data)
                    
                elif orig == ID_SENSOR_OXIG:
                    O2 = data
                    on = 0
                    if data > MAX_O2 or data < MIN_O2:
                        send_ALERTA(orig, data)
                        on = 1
                    process_atuador_cmd(ID_ATUADOR_CIRC_AR, on)

                elif orig == ID_SENSOR_TEMP:
                    TEMP = data
                    # Flag para ativação do Atuador
                    on = 0
                    if data > MAX_TEMP or data < MIN_TEMP:
                        send_ALERTA(orig, data)
                        on = 1
                    process_atuador_cmd(ID_ATUADOR_AQUEC, on)
                        
                elif orig == ID_SENSOR_UMID:
                    UMID = data
                    # Flag para ativação do Atuador
                    on = 0
                    if data > MAX_UMID or data < MIN_UMID:
                        send_ALERTA(orig, data)
                        on = 1
                    process_atuador_cmd(ID_ATUADOR_UMID, on)
                        
            elif ID_msg == REQ_LEITURA:
                print(f"[GERENCIADOR] RECEBIDO: REQ_LEITURA do ID {orig}")
                ID = struct.unpack('!i', payload)[0]
                conn.sendall(msg_RES_LEITURA(ID))
                print(f"[GERENCIADOR] ENVIADO: RES_LEITURA para o destino ID {orig} com ID {ID}")

            elif ID_msg == CONFIG:
                ID_func = payload[0] & 0b11
                min = struct.unpack('!f', payload[1:5])[0]
                max = struct.unpack('!f', payload[5:9])[0]

                metricas = {0: "TEMPERATURA", 1: "UMIDADE", 2: "OXIGENAÇÃO", 3: "BATIMENTOS"}
                nome_metrica = metricas.get(ID_func, "DESCONHECIDO")
                print(f"[CLIENTE {orig}] Configurou {nome_metrica}: MIN = {min:.2f} | MAX = {max:.2f}")

                if ID_func == 0:
                    MIN_TEMP = min
                    MAX_TEMP = max
                elif ID_func == 1:
                    MIN_BAT = min
                    MAX_BAT = max
                elif ID_func == 2:
                    MIN_UMID = min
                    MAX_UMID = max
                elif ID_func == 3:
                    MIN_O2 = min
                    MAX_O2 = max

            elif ID_msg == ACK_CMD:
                # Trata as respostas dos atuadores (Sucesso ou Erro interno)
                status_atuador = payload[0]
                if status_atuador == OK:
                    atuadores_ack[orig] = atuadores_req[orig]
                    atuadores_timeout_count[orig] = 0
                    atuadores_error_count[orig] = 0
                    print(f"[GERENCIADOR] Recebido ACK (OK) do Atuador {orig}.")
                elif status_atuador == ERROR:
                    atuadores_error_count[orig] += 1
                    if atuadores_error_count[orig] <= 3:
                        print(f"[GERENCIADOR] Atuador {orig} falhou internamente. Tentativa imediata {atuadores_error_count[orig]}/3...")
                        send_CMD_ATUADOR(orig, atuadores_req[orig])
                    else:
                        print(f"[GERENCIADOR] Falha persistente no Atuador {orig} após 3 tentativas.")
                        send_ALERTA(orig=orig, flag=ERROR)
                
    except ConnectionResetError:
        print(f"[GERENCIADOR] Conexão com {addr} perdida.")
    finally:
        if ID_disp in connections:
            del connections[ID_disp] # Remove da lista quando cair
        conn.close()


def start_gerenciador():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print("[GERENCIADOR] Iniciado e aguardando conexões...")
        
        while True:
            conn, addr = s.accept()
            # Inicia threads para manter a conexão persistente com o sensor/atuador/cliente 
            thread = threading.Thread(target=connection, args=(conn, addr))
            thread.start()

if __name__ == "__main__":
    start_gerenciador()