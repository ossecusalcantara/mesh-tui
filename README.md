# mesh-tui

TUI (interface de terminal) para redes [Meshtastic](https://meshtastic.org) construída com o
[SDK Python oficial](https://github.com/meshtastic/python) e o framework [Textual](https://textual.textualize.io/).

Conecte-se a um rádio via USB ou TCP, converse por canal ou mensagem direta, acompanhe os nós
da malha com telemetria e posição — tudo sem sair do terminal.

![mesh-tui em execução](docs/screenshot.svg)

## Funcionalidades

- **Conexão serial ou TCP** — auto-detecção de portas ou host `ip[:porta]` (padrão 4403)
- **Reconexão automática** — backoff exponencial (1s → 30s) quando o rádio ou a rede cai;
  desconexão manual (F3) cancela as tentativas
- **Confirmação de entrega** — cada mensagem enviada rastreia ACK/NAK (`✓` entregue, `✗`
  falhou, `…` pendente)
- **Histórico persistente** — SQLite em `~/.local/share/mesh_tui/history.db` (respeita
  `XDG_DATA_HOME`); tudo sobrevive a reinícios
- **Conversas separadas** — uma aba por canal (nome real, ex: LongFast) e abas de DM criadas
  sob demanda, com badge de não lidas (`N2 (3)`)
- **Tabela de nós** — SNR, hops, bateria e última vez visto, atualizada ao vivo
- **Painel de detalhes do nó** — Enter na tabela abre papel, hardware, posição com
  distância/direção do nó local (ex: `911 m a LSE`), telemetria do dispositivo (tensão, uso do
  canal, uptime) e de ambiente (temperatura, umidade, pressão)
- **Detecção de nó novo** — log + notificação quando um nó desconhecido aparece na malha
- **Erros acionáveis** — sem permissão na serial? A mensagem diz como corrigir (`dialout`)

## Requisitos

- Python 3.10+
- Um rádio Meshtastic acessível via USB (serial) ou TCP (nó com WiFi/ethernet)

## Instalação

```bash
git clone <repo> mesh_tui && cd mesh_tui
make install        # cria .venv e instala dependências + pacote em modo editável
```

Ou manualmente:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
```

Permissão de porta serial (Linux): adicione-se ao grupo `dialout` e refaça o login:

```bash
sudo usermod -aG dialout $USER
```

## Uso

```bash
make run                          # abre a TUI; conecte com F2
make run-serial PORT=/dev/ttyUSB0
make run-tcp HOST=192.168.1.50

# ou diretamente
mesh-tui --port /dev/ttyUSB0      # entry point instalado
mesh-tui --host 192.168.1.50
```

### Teclas

| Tecla              | Ação                                        |
|--------------------|---------------------------------------------|
| `F2`               | Conectar (diálogo serial/TCP)               |
| `F3`               | Desconectar (cancela reconexão automática)  |
| `F4`               | Atualizar lista de nós                      |
| `enter` / `ctrl+s` | Enviar mensagem                             |
| `enter` (tabela)   | Abrir detalhes do nó selecionado            |
| `esc`              | Fechar diálogo/detalhes                     |
| `ctrl+q`           | Sair                                        |

### Conversas

- A **aba ativa** define o canal do envio (broadcast).
- Selecione um **Destino** (nó específico) e envie para criar/trocar automaticamente para a
  aba de DM com esse nó.
- Mensagens diretas recebidas criam a aba da conversa e incrementam o badge de não lidas.

## Solução de problemas

| Mensagem                                 | Causa provável / solução                                    |
|------------------------------------------|-------------------------------------------------------------|
| sem permissão na porta serial            | `sudo usermod -aG dialout $USER` e refaça o login           |
| porta serial não encontrada              | confira o caminho (`ls /dev/ttyUSB*`)                       |
| porta serial ocupada                     | feche outro cliente Meshtastic usando o rádio               |
| conexão TCP recusada                     | confira host/porta e se o nó aceita clientes TCP            |
| múltiplas portas seriais detectadas      | escolha uma porta específica em vez de auto-detectar        |

## Desenvolvimento

```bash
make test        # testes headless (sem hardware)
make check       # testes + verificação de import
make clean       # remove caches
```

Os testes rodam a UI completa com `textual.run_test()` usando uma interface Meshtastic
simulada — cobrem conexão, reconexão, ACKs, histórico, DMs e o painel de detalhes.

### Arquitetura

| Módulo                    | Responsabilidade                                            |
|---------------------------|-------------------------------------------------------------|
| `mesh_tui/app.py`         | UI Textual: abas, composer, tabela, diálogos, eventos       |
| `mesh_tui/meshtastic_link.py` | Wrapper thread-safe do SDK: conexão, pubsub, reconexão, ACKs |
| `mesh_tui/storage.py`     | Histórico persistente em SQLite                             |
| `mesh_tui/nodeinfo.py`    | Posição (haversine/bearing), telemetria e painel de detalhes |

Fluxo de eventos: o SDK publica em threads próprias → `MeshtasticLink` normaliza em eventos
(`text`, `node`, `connected`, `disconnected`, `reconnect_failed`, `ack`) → a app faz marshal
para a thread da UI via `call_from_thread`.
