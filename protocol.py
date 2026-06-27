# IDs dos Dispositivos
ID_GERENCIADOR = 0 
ID_SENSOR_TEMP = 1 
ID_SENSOR_UMID = 2 
ID_ATUADOR_AQUEC = 5 

# IDs das Mensagens
REQ_REGISTRO = 0 
ACK_REGISTRO = 1 
ENVIO_DADOS = 2 
CMD_ATUADOR = 3
ACK_CMD = 4
REQ_LEITURA = 5
RES_LEITURA = 6
ALERTA = 7
CONFIG = 8

def pack_header(orig, dest, msg_id, payload_size):
    """
    Empacota o cabeçalho de 19 bits em 3 bytes (24 bits).
    Formato em bits: [5 bits padding] [4 origem] [4 destino] [4 msg_id] [7 payload_size]
    """
    header_int = (orig << 15) | (dest << 11) | (msg_id << 7) | payload_size
    return header_int.to_bytes(3, byteorder='big')

def unpack_header(data):
    """
    Lê 3 bytes e extrai os campos do cabeçalho.
    """
    header_int = int.from_bytes(data, byteorder='big')
    orig = (header_int >> 15) & 0b1111
    dest = (header_int >> 11) & 0b1111
    msg_id = (header_int >> 7) & 0b1111
    payload_size = header_int & 0b1111111
    return orig, dest, msg_id, payload_size