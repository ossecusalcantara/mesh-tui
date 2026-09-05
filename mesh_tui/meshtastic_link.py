"""meshtastic_link - wrapper thread-safe em volta do SDK Python do Meshtastic."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from pubsub import pub

import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface

logger = logging.getLogger(__name__)

TOPIC_TEXT = "meshtastic.receive.text"
TOPIC_CONN_ESTABLISHED = "meshtastic.connection.established"
TOPIC_CONN_LOST = "meshtastic.connection.lost"
TOPIC_NODE_UPDATED = "meshtastic.node.updated"
TOPIC_POSITION = "meshtastic.receive.position"
TOPIC_TELEMETRY = "meshtastic.receive.telemetry"

RECONNECT_MIN_DELAY = 1.0
RECONNECT_MAX_DELAY = 30.0

EventCallback = Callable[[str, dict[str, Any]], None]


def describe_error(exc: BaseException) -> str:
    """Traduz exceções de conexão em mensagens acionáveis para o usuário."""
    if isinstance(exc, SystemExit):
        return "múltiplas portas seriais detectadas — escolha uma porta específica"
    message = str(exc) or type(exc).__name__
    lowered = message.lower()
    if isinstance(exc, PermissionError) or "permission denied" in lowered:
        return (
            "sem permissão na porta serial — adicione-se ao grupo 'dialout' "
            "(sudo usermod -aG dialout $USER) e refaça o login"
        )
    if isinstance(exc, FileNotFoundError) or "no such file or directory" in lowered:
        return "porta serial não encontrada — verifique o caminho (ex: /dev/ttyUSB0)"
    if isinstance(exc, ConnectionRefusedError) or "connection refused" in lowered:
        return "conexão TCP recusada — confira o host e se o nó aceita clientes TCP"
    if isinstance(exc, TimeoutError) or "timed out" in lowered or "timeout" in lowered:
        return "tempo esgotado ao conectar — o nó está acessível?"
    if "device is busy" in lowered or "resource busy" in lowered or "errno 16" in lowered:
        return "porta serial ocupada — feche outros programas usando o rádio"
    return f"{type(exc).__name__}: {message}"


def detect_serial_ports() -> list[str]:
    """Retorna lista de portas seriais candidatas (pode ser vazia)."""
    try:
        ports = meshtastic.util.findPorts()
        if isinstance(ports, str):
            ports = [ports]
        return list(ports or [])
    except Exception:
        return []


class MeshtasticLink:
    """Encapsula a interface do SDK Meshtastic e publica eventos para listeners.

    - Reconecta automaticamente (backoff exponencial) quando a conexão cai.
    - Rastreia ACKs de mensagens enviadas com wantAck.

    Os callbacks são sempre invocados em threads do SDK (leitura serial /
    publishing thread) — o consumidor é responsável por fazer marshal para
    a thread da UI.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._interface: Any = None
        self._listeners: list[EventCallback] = []
        self._subscribed = False
        self._last_spec: tuple[str, str] | None = None
        self._generation = 0
        self._retry_thread: threading.Thread | None = None
        self._awaiting_acks: dict[int, str] = {}

    # ------------------------------------------------------------------ state
    @property
    def interface(self) -> Any:
        with self._lock:
            return self._interface

    @property
    def connected(self) -> bool:
        iface = self.interface
        try:
            return bool(iface is not None and iface.isConnected.is_set())
        except Exception:
            return False

    @property
    def reconnecting(self) -> bool:
        thread = self._retry_thread
        return thread is not None and thread.is_alive()

    # ------------------------------------------------------------ connections
    def connect(self, kind: str, target: str) -> None:
        """Conecta ('serial', porta) | ('tcp', 'host[:porta]'). Bloqueante."""
        self._cancel_retries()
        try:
            self._attempt(kind, target)
        except ConnectionError:
            raise
        except (Exception, SystemExit) as exc:
            raise ConnectionError(describe_error(exc)) from exc
        with self._lock:
            self._last_spec = (kind, target)
        logger.info("Conectado: %s %s", kind, target or "auto")

    def connect_serial(self, port: str | None = None) -> None:
        self.connect("serial", port or "")

    def connect_tcp(self, hostname: str, port: int = 4403) -> None:
        self.connect("tcp", f"{hostname}:{port}")

    def _attempt(self, kind: str, target: str) -> None:
        self._close_interface()
        label = f"{kind} {target or 'auto'}"
        if kind == "tcp":
            host, _, port = target.partition(":")
            iface = meshtastic.tcp_interface.TCPInterface(
                hostname=host, portNumber=int(port) if port else 4403
            )
        elif kind == "serial":
            iface = meshtastic.serial_interface.SerialInterface(devPath=target or None)
        else:
            raise ConnectionError(f"tipo de conexão desconhecido: {kind}")
        failure = getattr(iface, "failure", None)
        try:
            established = bool(iface.isConnected.is_set())
        except Exception:
            established = False
        if failure or not established:
            reason = failure or "nenhum nó Meshtastic respondeu"
            try:
                iface.close()
            except Exception:
                pass
            raise ConnectionError(f"não foi possível conectar ({label}): {reason}")
        with self._lock:
            self._interface = iface
        self._subscribe()

    def _close_interface(self) -> None:
        with self._lock:
            iface, self._interface = self._interface, None
        if iface is None:
            return
        try:
            iface.close()
        except Exception as exc:
            logger.debug("Erro ao fechar interface: %s", exc)

    def disconnect(self) -> None:
        self._cancel_retries()
        with self._lock:
            self._last_spec = None
        self._close_interface()

    # -------------------------------------------------------------- retry loop
    def _cancel_retries(self) -> None:
        with self._lock:
            self._generation += 1
            self._retry_thread = None

    def _start_retries(self) -> None:
        with self._lock:
            spec = self._last_spec
            if spec is None or self._retry_thread is not None:
                return
            self._generation += 1
            generation = self._generation
            thread = threading.Thread(
                target=self._retry_loop,
                args=(generation, spec),
                daemon=True,
                name="mesh-tui-reconnect",
            )
            self._retry_thread = thread
        thread.start()

    def _generation_is(self, generation: int) -> bool:
        with self._lock:
            return self._generation == generation

    def _sleep_interruptible(self, seconds: float, generation: int) -> bool:
        deadline = time.monotonic() + seconds
        while True:
            if not self._generation_is(generation):
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            time.sleep(min(remaining, 0.2))

    def _retry_loop(self, generation: int, spec: tuple[str, str]) -> None:
        delay = RECONNECT_MIN_DELAY
        attempt = 0
        while True:
            if not self._sleep_interruptible(delay, generation):
                return
            attempt += 1
            try:
                self._attempt(*spec)
            except ConnectionError as exc:
                error = str(exc)
            except (Exception, SystemExit) as exc:
                error = describe_error(exc)
            else:
                with self._lock:
                    if self._generation == generation:
                        self._retry_thread = None
                self._emit("connected", {})
                return
            self._emit(
                "reconnect_failed",
                {"attempt": attempt, "error": error, "next_delay": delay},
            )
            if not self._sleep_interruptible(delay, generation):
                return
            delay = min(delay * 2.0, RECONNECT_MAX_DELAY)
    # --------------------------------------------------------------- messaging
    def send_text(
        self, text: str, channel_index: int = 0, destination: str = "^all"
    ) -> int | None:
        iface = self.interface
        if iface is None:
            raise ConnectionError("Não conectado a nenhum nó.")
        packet = iface.sendText(
            text=text,
            destinationId=destination,
            channelIndex=channel_index,
            wantAck=True,
            onResponse=self.onAckNak,
        )
        packet_id = getattr(packet, "id", None)
        if packet_id:
            with self._lock:
                self._awaiting_acks[int(packet_id)] = text
                while len(self._awaiting_acks) > 128:
                    self._awaiting_acks.pop(next(iter(self._awaiting_acks)))
        return int(packet_id) if packet_id else None

    def onAckNak(self, packet: dict[str, Any] | None = None) -> None:
        """Callback do SDK (nome exigido pela convenção dele) para ACK/NAK."""
        decoded = (packet or {}).get("decoded", {})
        request_id = decoded.get("requestId")
        text = ""
        if request_id is not None:
            try:
                key = int(request_id)
            except (TypeError, ValueError):
                key = None
            if key is not None:
                with self._lock:
                    text = self._awaiting_acks.pop(key, "")
        self._emit("ack", {"packet": packet or {}, "text": text})

    # -------------------------------------------------------------------- data
    def nodes(self) -> dict[int, dict[str, Any]]:
        iface = self.interface
        if iface is None:
            return {}
        return dict(getattr(iface, "nodesByNum", None) or {})

    def channels(self) -> list[dict[str, Any]]:
        """Canais habilitados do nó local: [{'index': int, 'name': str, 'role': str}]."""
        iface = self.interface
        if iface is None:
            return []
        out: list[dict[str, Any]] = []
        try:
            for ch in iface.localNode.channels:
                role = str(getattr(ch, "role", "UNKNOWN"))
                if role.startswith("ROLE_"):
                    role = role[5:]
                if role in ("DISABLED", "NOT_SET"):
                    continue
                name = getattr(ch.settings, "name", "") or f"CH{ch.index}"
                out.append({"index": ch.index, "name": name, "role": role})
        except Exception as exc:
            logger.debug("Falha ao ler canais: %s", exc)
        return out

    def node_name(self, node_num: int | str | None) -> str:
        """Resolve um número/ID de nó para nome amigável."""
        try:
            node_num_i = int(node_num)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return str(node_num) if node_num is not None else "?"
        iface = self.interface
        if iface is not None:
            node = (getattr(iface, "nodesByNum", None) or {}).get(node_num_i)
            if node:
                user = node.get("user", {})
                name = user.get("shortName") or user.get("longName")
                if name:
                    return name
        return f"!{node_num_i:08x}"

    # ---------------------------------------------------------------- listeners
    def add_listener(self, callback: EventCallback) -> None:
        self._listeners.append(callback)

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        for callback in list(self._listeners):
            try:
                callback(event, payload)
            except Exception:
                logger.exception("Erro em listener de evento %s", event)

    # ------------------------------------------------------------- pubsub glue
    def _subscribe(self) -> None:
        if self._subscribed:
            return
        pub.subscribe(self._on_text, TOPIC_TEXT)
        pub.subscribe(self._on_conn_established, TOPIC_CONN_ESTABLISHED)
        pub.subscribe(self._on_conn_lost, TOPIC_CONN_LOST)
        pub.subscribe(self._on_node_updated, TOPIC_NODE_UPDATED)
        pub.subscribe(self._on_node_packet, TOPIC_POSITION)
        pub.subscribe(self._on_node_packet, TOPIC_TELEMETRY)
        self._subscribed = True

    def _unsubscribe(self) -> None:
        if not self._subscribed:
            return
        for topic, handler in (
            (TOPIC_TEXT, self._on_text),
            (TOPIC_CONN_ESTABLISHED, self._on_conn_established),
            (TOPIC_CONN_LOST, self._on_conn_lost),
            (TOPIC_NODE_UPDATED, self._on_node_updated),
            (TOPIC_POSITION, self._on_node_packet),
            (TOPIC_TELEMETRY, self._on_node_packet),
        ):
            try:
                pub.unsubscribe(handler, topic)
            except Exception:
                pass
        self._subscribed = False

    def _is_current(self, interface: Any) -> bool:
        return interface is not None and interface is self.interface

    def _on_text(self, packet: dict[str, Any] | None = None, interface: Any = None) -> None:
        if self._is_current(interface) and packet:
            self._emit("text", {"packet": packet})

    def _on_conn_established(self, interface: Any = None) -> None:
        if self._is_current(interface):
            self._emit("connected", {})

    def _on_conn_lost(self, interface: Any = None) -> None:
        if self._is_current(interface):
            self._start_retries()
            self._emit("disconnected", {})

    def _on_node_updated(
        self, node: dict[str, Any] | None = None, interface: Any = None
    ) -> None:
        if self._is_current(interface) and node:
            self._emit("node", {"node": node})

    def _on_node_packet(
        self, packet: dict[str, Any] | None = None, interface: Any = None
    ) -> None:
        """Posição/telemetria recebida — o SDK já atualizou o nodeDB."""
        if self._is_current(interface) and packet:
            self._emit("node", {"node": {"num": packet.get("from")}})
