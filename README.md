# Protocolo de Comunicação para Incubadora Neonatal

Este repositório contém a implementação de um protocolo da camada de aplicação customizado para o monitoramento e controle de uma incubadora neonatal. O sistema foi desenvolvido em **Python 3** utilizando **Sockets TCP/IP**, com uso de *threads*.
O objetivo do sistema é garantir o funcionamento seguro de uma incubadora através da leitura contínua de sensores vitais e ambientais. Se as métricas ultrapassarem os limites de segurança configurados, o servidor central (Gerenciador) aciona automaticamente os atuadores correspondentes para corrigir o ambiente e envia alertas em tempo real para a interface de monitoramento (Cliente).

## Arquitetura e Componentes

O sistema é dividido em processos independentes que se comunicam via rede local (`127.0.0.1` na porta `3000`).

* **`protocol.py`**: Biblioteca base compartilhada por todos os componentes. Define os IDs dos dispositivos, tipos de mensagens, o dicionário `NOMES_DISPOSITIVOS` para exibição descritiva e as funções `pack_header` e `unpack_header` para formatação do cabeçalho de 3 bytes (19 bits compactados).
* **`ambiente.py`**: Simulador das leis físicas da incubadora. Executa a termodinâmica simulada e expõe uma porta UDP local (`5000`) para que os atuadores corrijam o ambiente físico e os sensores realizem leituras físicas contínuas das grandezas.
* **`gerenciador.py`**: Atua como o Servidor central. Recebe conexões, armazena o estado atual dos sensores, gerencia os atuadores através de comandos liga/desliga (`CMD_ATUADOR`) e lida com retransmissões baseadas em timeout.
* **`sensor.py`**: Simula os sensores operando simultaneamente via *threads*: Temperatura, Umidade, Oxigenação e Batimentos Cardíacos. Eles realizam leituras no simulador UDP e enviam os dados (`ENVIO_DADOS`) em float de 32 bits a cada 1 segundo ao Gerenciador após o registro.
* **`atuador.py`**: Simula os atuadores vitais: Aquecimento, Circulação do Ar e Umidade. Eles se conectam ao Gerenciador, aguardam comandos e aplicam as alterações físicas no simulador UDP, respondendo com confirmações (`ACK_CMD`).
* **`cliente.py`**: Interface interativa do usuário. Permite solicitar a leitura do valor atual de um sensor específico, reconfigurar os limites de cada métrica e ouvir alertas assíncronos gerados pelo Gerenciador caso algo saia do controle.

## Como Executar

### Pré-requisitos
* Sistema Operacional: Linux, macOS ou Windows.
* Interpretador: **Python 3.8** ou superior.
* Nenhuma dependência externa é necessária (utiliza apenas bibliotecas nativas como `socket`, `struct` e `threading`).

### Passo a Passo

Como cada arquivo representa um processo (ou conjunto de processos) diferente, você precisará abrir **cinco terminais** separados.

**1. Inicie o Simulador de Ambiente**  
No primeiro terminal, ligue o simulador de leis físicas do ambiente:
```bash
python ambiente.py
```

**2. Inicie o Servidor Central (Gerenciador)**  
No segundo terminal, inicie o servidor que irá gerenciar todas as conexões:
```bash
python gerenciador.py
```

**3. Conecte os Atuadores**  
No terceiro terminal, ligue os dispositivos atuadores:
```bash
python atuador.py
```

**4. Conecte os Sensores**  
No quarto terminal, inicie a leitura e o envio contínuo dos dados físicos:
```bash
python sensor.py
```

**5. Abra o Terminal de Controle (Cliente)**  
No quinto e último terminal, inicie a interface de monitoramento e configuração:
```bash
python cliente.py
```


## Funcionalidades do Protocolo

* **Handshake de Registro:** Sensores e Atuadores precisam enviar uma requisição de registro (`REQ_REGISTRO`) e receber aprovação (`ACK_REGISTRO`) antes de operarem.
* **Monitoramento Contínuo:** Sensores realizam leituras aleatórias dentro de faixas seguras e enviam ao servidor ininterruptamente.
* **Controle Automático:** Se um sensor (ex: Temperatura) ler um valor fora do escopo, o Gerenciador aciona automaticamente o atuador correspondente (ex: Aquecimento).
* **Comunicação Assíncrona:** O Cliente utiliza uma *thread daemon* para receber alertas críticos em tempo real, sem bloquear a navegação no menu principal.
* **Redundância:** O Gerenciador conta com um mecanismo de *timeout* (3 segundos) para atuadores; caso um comando não seja confirmado (`ACK_CMD`), ele retransmite o pacote. Se falhar consecutivamente, um erro de sistema é repassado ao Cliente.
