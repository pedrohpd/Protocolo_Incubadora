# Protocolo de Comunicação para Incubadora Neonatal

Este repositório contém a implementação de um protocolo da camada de aplicação customizado para o monitoramento e controle de uma incubadora neonatal. O sistema foi desenvolvido em **Python 3** utilizando **Sockets TCP/IP**, com uso de *threads*.
O objetivo do sistema é garantir o funcionamento seguro de uma incubadora através da leitura contínua de sensores vitais e ambientais. Se as métricas ultrapassarem os limites de segurança configurados, o servidor central (Gerenciador) aciona automaticamente os atuadores correspondentes para corrigir o ambiente e envia alertas em tempo real para a interface de monitoramento (Cliente).

## Arquitetura e Componentes

O sistema é dividido em processos independentes que se comunicam via rede local (`127.0.0.1` na porta `3000`).

* **`protocol.py`**: Biblioteca base compartilhada por todos os componentes. Define os IDs dos dispositivos, tipos de mensagens e as funções `pack_header` e `unpack_header`, que formatam o cabeçalho do protocolo (19 bits compactados em 3 bytes) e anexam o payload.
* **`gerenciador.py`**: Atua como o Servidor central. Recebe conexões, armazena o estado atual dos sensores, gerencia os atuadores através de comandos liga/desliga (`CMD_ATUADOR`) e lida com retransmissões baseadas em timeout.
* **`sensores.py`**: Simula quatro sensores operando simultaneamente via *threads*: Temperatura, Umidade, Oxigenação e Batimentos Cardíacos. Eles enviam dados (`ENVIO_DADOS`) em float de 32 bits a cada 1 segundo após o registro bem-sucedido.
* **`atuadores.py`**: Simula três atuadores vitais: Aquecimento, Circulação do Ar e Umidade. Eles se conectam ao Gerenciador, aguardam comandos e respondem com confirmações (`ACK_CMD`).
* **`cliente.py`**: Interface interativa do usuário. Permite solicitar a leitura do valor atual de um sensor específico, reconfigurar os valores mínimos e máximos de cada métrica e ouvir alertas assíncronos gerados pelo Gerenciador caso algo saia do controle.

## Como Executar

### Pré-requisitos
* Sistema Operacional: Linux, macOS ou Windows.
* Interpretador: **Python 3.8** ou superior.
* Nenhuma dependência externa é necessária (utiliza apenas bibliotecas nativas como `socket`, `struct` e `threading`).

### Passo a Passo

Como cada arquivo representa um processo (ou conjunto de processos) diferente, você precisará abrir **quatro terminais** separados.

**1. Inicie o Servidor Central (Gerenciador)**  
No primeiro terminal, inicie o servidor que irá gerenciar todas as conexões:

```bash
python gerenciador.py
```

**2. Conecte os Atuadores**  
No segundo terminal, ligue os dispositivos que vão corrigir as falhas na incubadora:
```bash
python atuador.py
```

**3. Conecte os Sensores**  
No terceiro terminal, inicie o envio de dados vitais simulados:
```bash
python sensor.py
```


**4. Abra o Terminal de Controle (Cliente)**  
No quarto e último terminal, inicie a interface do usuário:
```bash
python cliente.py
```


## Funcionalidades do Protocolo

* **Handshake de Registro:** Sensores e Atuadores precisam enviar uma requisição de registro (`REQ_REGISTRO`) e receber aprovação (`ACK_REGISTRO`) antes de operarem.
* **Monitoramento Contínuo:** Sensores realizam leituras aleatórias dentro de faixas seguras e enviam ao servidor ininterruptamente.
* **Controle Automático:** Se um sensor (ex: Temperatura) ler um valor fora do escopo, o Gerenciador aciona automaticamente o atuador correspondente (ex: Aquecimento).
* **Comunicação Assíncrona:** O Cliente utiliza uma *thread daemon* para receber alertas críticos em tempo real, sem bloquear a navegação no menu principal.
* **Redundância:** O Gerenciador conta com um mecanismo de *timeout* (3 segundos) para atuadores; caso um comando não seja confirmado (`ACK_CMD`), ele retransmite o pacote. Se falhar consecutivamente, um erro de sistema é repassado ao Cliente.
