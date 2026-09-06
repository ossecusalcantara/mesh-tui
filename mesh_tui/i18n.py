"""Minimal i18n for UI strings. English is the default; Portuguese is available."""

from __future__ import annotations

import os

EN = {
    "app.description": "TUI for Meshtastic networks (Python SDK + Textual).",
    "subtitle.disconnected": "disconnected",
    "subtitle.connected": "connected · {name}",
    "welcome": "Disconnected — press F2 to connect",
    "help.line": (
        "F2 connect · F3 disconnect · F4 refresh nodes · ctrl+q quit"
    ),
    "key.connect": "Connect",
    "key.disconnect": "Disconnect",
    "key.refresh_nodes": "Refresh nodes",
    "key.send": "Send",
    "key.quit": "Quit",
    "key.cancel": "Cancel",
    "key.close": "Close",
    "key.language": "Language",
    "notify.language": "Language: {name}",
    "lang.en": "English",
    "lang.pt": "Português",
    "col.node": "Node",
    "col.snr": "SNR",
    "col.hops": "Hops",
    "col.battery": "Battery",
    "col.seen": "Seen",
    "connect.title": "Connect to Meshtastic node",
    "connect.serial.label": "Serial port:",
    "connect.tcp.label": "Or TCP host (e.g. 192.168.1.50):",
    "connect.tcp.placeholder": "leave empty to use serial",
    "connect.hint": "Fill in the serial port OR the TCP host",
    "connect.button": "Connect [enter]",
    "connect.cancel": "Cancel [esc]",
    "status.connecting": "Connecting ({kind}: {target})...",
    "status.tcp.empty": "TCP host is empty.",
    "status.connect.failed": "Connection failed: {message}",
    "status.disconnected": "Disconnected — press F2 to connect",
    "status.lost.reconnecting": "Connection lost — reconnecting automatically...",
    "status.lost": "Connection lost.",
    "status.reconnecting": "Reconnecting (attempt {n})...",
    "status.nodes.refreshed": "Nodes updated: {n}",
    "status.connected": "Connected as {name} · channels: {channels}",
    "log.disconnected": "Disconnected.",
    "log.lost.reconnecting": "Connection lost. Reconnecting...",
    "log.lost": "Connection lost.",
    "log.reconnect.failed": "Reconnect failed: {error}",
    "log.connected": "Connected as {name}.",
    "log.new.node": "New node on the mesh: {name}",
    "log.send.failed": "failed to send: {error}",
    "notify.new.node": "{name} joined the mesh",
    "notify.new.node.title": "New node",
    "ack.delivered": "delivered to {name}{snippet}",
    "ack.not.delivered": "not delivered to {name} ({reason}){snippet}",
    "actor.system": "system",
    "actor.me": "me",
    "actor.error": "error",
    "node.role": "role {value}",
    "node.hardware": "hardware {value}",
    "node.snr": "SNR {value} dB",
    "node.hops": "{n} hop(s)",
    "node.seen": "seen {ago}",
    "node.favorite": "favorite",
    "node.via.mqtt": "via MQTT",
    "node.position": "Position: {lat}, {lon}{alt}",
    "node.distance": "{dist} {dir} from local node",
    "node.device": "Device",
    "node.environment": "Environment",
    "node.battery": "battery {level}%",
    "node.voltage": "{value} V",
    "node.channel.util": "channel use {value}%",
    "node.air.tx": "TX air {value}%",
    "node.uptime": "uptime {value}",
    "node.temp": "{value} °C",
    "node.humidity": "{value}% RH",
    "node.pressure": "{value} hPa",
    "node.now": "now",
    "composer.destination": "Destination",
    "composer.broadcast": "📡 Broadcast",
    "composer.placeholder": "Message... (enter/ctrl+s sends)",
    "err.multiple.ports": "multiple serial ports detected — choose a specific port",
    "err.permission": (
        "no permission on the serial port — add yourself to the 'dialout' group"
        " (sudo usermod -aG dialout $USER) and log in again"
    ),
    "err.not.found": "serial port not found — check the path (e.g. /dev/ttyUSB0)",
    "err.refused": (
        "TCP connection refused — check the host and that the node accepts"
        " TCP clients"
    ),
    "err.timeout": "timed out connecting — is the node reachable?",
    "err.busy": "serial port busy — close other programs using the radio",
    "err.unknown.kind": "unknown connection type: {kind}",
    "err.not.connected": "Not connected to any node.",
    "err.connect.failed": "unable to connect ({label}): {reason}",
    "err.no.response": "no Meshtastic node responded",
    "cli.help.port": "radio serial port (e.g. /dev/ttyUSB0)",
    "cli.help.host": "node TCP host (e.g. 192.168.1.50[:4403])",
    "cli.help.lang": "UI language (default: auto-detect)",
}

PT = {
    "app.description": "TUI para redes Meshtastic (SDK Python + Textual).",
    "subtitle.disconnected": "desconectado",
    "subtitle.connected": "conectado · {name}",
    "welcome": "Desconectado — pressione F2 para conectar",
    "help.line": (
        "F2 conectar · F3 desconectar · F4 atualizar nós · ctrl+q sair"
    ),
    "key.connect": "Conectar",
    "key.disconnect": "Desconectar",
    "key.refresh_nodes": "Atualizar nós",
    "key.send": "Enviar",
    "key.quit": "Sair",
    "key.cancel": "Cancelar",
    "key.close": "Fechar",
    "key.language": "Idioma",
    "notify.language": "Idioma: {name}",
    "lang.en": "English",
    "lang.pt": "Português",
    "col.node": "Nó",
    "col.snr": "SNR",
    "col.hops": "Hops",
    "col.battery": "Bateria",
    "col.seen": "Visto",
    "connect.title": "Conectar ao nó Meshtastic",
    "connect.serial.label": "Porta serial:",
    "connect.tcp.label": "Ou host TCP (ex: 192.168.1.50):",
    "connect.tcp.placeholder": "deixe vazio p/ usar serial",
    "connect.hint": "Preencha a porta serial OU o host TCP",
    "connect.button": "Conectar [enter]",
    "connect.cancel": "Cancelar [esc]",
    "status.connecting": "Conectando ({kind}: {target})...",
    "status.tcp.empty": "Host TCP vazio.",
    "status.connect.failed": "Falha ao conectar: {message}",
    "status.disconnected": "Desconectado — pressione F2 para conectar",
    "status.lost.reconnecting": "Conexão perdida — reconectando automaticamente...",
    "status.lost": "Conexão perdida.",
    "status.reconnecting": "Reconectando (tentativa {n})...",
    "status.nodes.refreshed": "Nós atualizados: {n}",
    "status.connected": "Conectado como {name} · canais: {channels}",
    "log.disconnected": "Desconectado.",
    "log.lost.reconnecting": "Conexão perdida. Reconectando...",
    "log.lost": "Conexão perdida.",
    "log.reconnect.failed": "Reconexão falhou: {error}",
    "log.connected": "Conectado como {name}.",
    "log.new.node": "Nó novo na rede: {name}",
    "log.send.failed": "falha ao enviar: {error}",
    "notify.new.node": "{name} entrou na rede",
    "notify.new.node.title": "Nó novo",
    "ack.delivered": "entregue para {name}{snippet}",
    "ack.not.delivered": "não entregue para {name} ({reason}){snippet}",
    "actor.system": "sistema",
    "actor.me": "eu",
    "node.role": "papel {value}",
    "node.hardware": "hardware {value}",
    "node.snr": "SNR {value} dB",
    "node.hops": "{n} hop(s)",
    "node.seen": "visto {ago}",
    "node.favorite": "favorito",
    "node.via.mqtt": "via MQTT",
    "node.position": "Posição: {lat}, {lon}{alt}",
    "node.distance": "{dist} a {dir} do nó local",
    "node.device": "Dispositivo",
    "node.environment": "Ambiente",
    "node.battery": "bateria {level}%",
    "node.voltage": "{value} V",
    "node.channel.util": "uso do canal {value}%",
    "node.air.tx": "ar TX {value}%",
    "node.uptime": "uptime {value}",
    "node.temp": "{value} °C",
    "node.humidity": "{value}% UR",
    "node.pressure": "{value} hPa",
    "node.now": "agora",
    "composer.destination": "Destino",
    "composer.broadcast": "📡 Broadcast",
    "composer.placeholder": "Mensagem... (enter/ctrl+s envia)",
    "err.multiple.ports": "múltiplas portas seriais detectadas — escolha uma porta específica",
    "err.permission": (
        "sem permissão na porta serial — adicione-se ao grupo 'dialout'"
        " (sudo usermod -aG dialout $USER) e refaça o login"
    ),
    "err.not.found": "porta serial não encontrada — verifique o caminho (ex: /dev/ttyUSB0)",
    "err.refused": (
        "conexão TCP recusada — confira o host e se o nó aceita clientes TCP"
    ),
    "err.timeout": "tempo esgotado ao conectar — o nó está acessível?",
    "err.busy": "porta serial ocupada — feche outros programas usando o rádio",
    "err.unknown.kind": "tipo de conexão desconhecido: {kind}",
    "err.not.connected": "Não conectado a nenhum nó.",
    "err.connect.failed": "não foi possível conectar ({label}): {reason}",
    "err.no.response": "nenhum nó Meshtastic respondeu",
    "cli.help.port": "porta serial do rádio (ex: /dev/ttyUSB0)",
    "cli.help.host": "host TCP do nó (ex: 192.168.1.50[:4403])",
    "cli.help.lang": "idioma da interface (padrão: auto-detectar)",
}

LANGUAGES: dict[str, dict[str, str]] = {"en": EN, "pt": PT}

_current = "en"


def normalize(name: str) -> str:
    """Normalize a locale name such as 'pt_BR.UTF-8' to 'pt'."""
    return name.replace("_", "-").split("-")[0].lower()


def set_language(lang: str) -> None:
    global _current
    key = normalize(lang)
    if key not in LANGUAGES:
        raise ValueError(f"unsupported language: {lang!r}")
    _current = key


def language() -> str:
    return _current


def language_name(lang: str | None = None) -> str:
    """Display name for a language code (e.g. 'pt' -> 'Português')."""
    key = normalize(lang) if lang else _current
    return LANGUAGES.get(key, EN).get(f"lang.{key}", key)


def next_language() -> str:
    """Next language in sorted order (cycles back to the first)."""
    langs = sorted(LANGUAGES)
    return langs[(langs.index(_current) + 1) % len(langs)]


def detect() -> str:
    """Pick a language from the environment locale, falling back to English."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value and normalize(value) in LANGUAGES:
            return normalize(value)
    return "en"


def t(key: str, **kwargs: object) -> str:
    """Translate a key, formatting with any given placeholders."""
    table = LANGUAGES.get(_current, EN)
    text = table.get(key) or EN.get(key) or key
    return text.format(**kwargs) if kwargs else text
