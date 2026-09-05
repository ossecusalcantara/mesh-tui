"""Aplicação Textual principal do TUI Meshtastic."""

from __future__ import annotations

import argparse
import datetime
import time
from typing import Any

from rich.markup import escape
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets._tabbed_content import ContentTab, ContentTabs

from .meshtastic_link import MeshtasticLink, detect_serial_ports
from .nodeinfo import ago_desc, render_details
from .storage import Message, MessageStore

BROADCAST = "^all"

MSG_HELP = "F2 conectar · F3 desconectar · F4 atualizar nós · ctrl+q sair"


class ConnectScreen(ModalScreen[tuple[str, str] | None]):
    """Diálogo de conexão. Dismiss com ('serial', porta) | ('tcp', host) | None."""

    CSS = """
    ConnectScreen {
        align: center middle;
    }
    #connect-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        padding: 1 2;
        width: 64;
        height: auto;
        border: thick $accent;
        background: $surface;
    }
    #connect-title {
        column-span: 2;
        text-align: center;
        text-style: bold;
    }
    #connect-hint {
        column-span: 2;
        text-align: center;
        color: $text-muted;
    }
    Button {
        width: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._ports = detect_serial_ports()

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar"),
    ]

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self._submit()

    def compose(self) -> ComposeResult:
        port_options = [("Auto-detectar", "")] + [(p, p) for p in self._ports]
        with Vertical(id="connect-dialog"):
            yield Static("Conectar ao nó Meshtastic", id="connect-title")
            yield Static("Porta serial:", classes="label")
            yield Select(port_options, id="serial-select", value="")
            yield Static("Ou host TCP (ex: 192.168.1.50):", classes="label")
            yield Input(placeholder="deixe vazio p/ usar serial", id="tcp-input")
            yield Static(
                "Preencha a porta serial OU o host TCP", id="connect-hint"
            )
            yield Button("Conectar [enter]", id="connect-btn", variant="primary")
            yield Button("Cancelar [esc]", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#serial-select", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect-btn":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        tcp_host = self.query_one("#tcp-input", Input).value.strip()
        serial_port = self.query_one("#serial-select", Select).value or ""
        if tcp_host:
            self.dismiss(("tcp", tcp_host))
        else:
            self.dismiss(("serial", str(serial_port)))


class NodeDetailScreen(ModalScreen[None]):
    """Painel com detalhes completos de um nó. Fechar com esc/enter."""

    CSS = """
    NodeDetailScreen {
        align: center middle;
    }
    #node-detail {
        width: 76;
        height: auto;
        max-height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("escape,enter", "close", "Fechar"),
    ]

    def __init__(self, markup: str) -> None:
        super().__init__()
        self._markup = markup

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="node-detail"):
            yield Static(self._markup, id="node-detail-text", markup=True)

    def action_close(self) -> None:
        self.dismiss(None)


class MeshTuiApp(App[None]):
    """TUI para redes Meshtastic usando o SDK Python + Textual."""

    TITLE = "Meshtastic TUI"
    SUB_TITLE = "desconectado"

    CSS = """
    #body { height: 1fr; }
    #left { width: 2fr; min-width: 40; }
    #conversations { height: 1fr; border: round $accent; }
    #conversations TabPane { height: 1fr; }
    #conversations RichLog { height: 1fr; }
    #composer { height: auto; padding: 0 1; }
    #nodes {
        width: 1fr;
        min-width: 36;
        border: round $success;
    }
    #status {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }
    Input { width: 1fr; }
    Select { width: 1fr; }
    #input-msg { width: 3fr; }
    """

    BINDINGS = [
        Binding("f2", "connect", "Conectar"),
        Binding("f3", "disconnect", "Desconectar"),
        Binding("f4", "refresh_nodes", "Atualizar nós"),
        Binding("ctrl+s", "send", "Enviar"),
        Binding("ctrl+q", "quit", "Sair"),
    ]

    def __init__(
        self,
        serial_port: str | None = None,
        tcp_host: str | None = None,
        store: MessageStore | None = None,
    ) -> None:
        super().__init__()
        self._serial_port = serial_port
        self._tcp_host = tcp_host
        self._channel_labels: dict[int, str] = {0: "CH0"}
        self.link = MeshtasticLink()
        self.link.add_listener(self._on_link_event)
        self._store = store if store is not None else MessageStore()
        self._titles: dict[str, str] = {}
        self._logs: dict[str, RichLog] = {}
        self._pane_conv: dict[str, str] = {}
        self._unread: dict[str, int] = {}
        self._dm_channel: dict[str, int] = {}
        self._ack_rows: dict[int, int] = {}
        self._row_conv: dict[int, str] = {}
        self._written: dict[str, int] = {}
        self._known_nodes: set[int] = set()
        self._nodes_synced = False

    # --------------------------------------------------------------- compose
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield TabbedContent(id="conversations")
                with Horizontal(id="composer"):
                    yield Select(
                        [("📡 Broadcast", BROADCAST)],
                        prompt="Destino",
                        id="dest-select",
                        allow_blank=False,
                        value=BROADCAST,
                    )
                    yield Input(
                        placeholder="Mensagem... (enter/ctrl+s envia)",
                        id="input-msg",
                    )
            yield DataTable(id="nodes")
        yield Static("Desconectado — pressione F2 para conectar", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#nodes", DataTable)
        table.add_columns("Nó", "SNR", "Hops", "Bateria", "Visto")
        table.cursor_type = "row"
        self._ensure_tab("ch:0", "CH0")
        self._system_log(MSG_HELP)

    # ---------------------------------------------------------------- helpers
    def _set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    @property
    def _active_conv(self) -> str:
        tabs = self.query_one("#conversations", TabbedContent)
        pane = tabs.active_pane
        if pane is None or pane.id is None:
            return "ch:0"
        return self._pane_conv.get(pane.id, "ch:0")

    # ------------------------------------------------------------------ tabs
    @staticmethod
    def _pane_id(conv: str) -> str:
        return "pane-" + conv.replace(":", "-")

    @staticmethod
    def _log_id(conv: str) -> str:
        return "log-" + conv.replace(":", "-")

    def _ensure_tab(self, conv: str, title: str) -> None:
        if conv in self._titles:
            if title and self._titles[conv] != title:
                self._titles[conv] = title
                self._set_tab_label(conv)
            return
        self._titles[conv] = title
        self._unread[conv] = 0
        log = RichLog(id=self._log_id(conv), markup=True, wrap=True)
        self._logs[conv] = log
        pane_id = self._pane_id(conv)
        self._pane_conv[pane_id] = conv
        self.query_one("#conversations", TabbedContent).add_pane(
            TabPane(title, log, id=pane_id)
        )
        for msg in self._store.recent(conv):
            self._render_stored(conv, msg)

    def _switch_tab(self, conv: str) -> None:
        if conv not in self._titles:
            return
        tabs = self.query_one("#conversations", TabbedContent)
        try:
            content_tabs = tabs.get_child_by_type(ContentTabs)
            content_tabs.active = ContentTab.add_prefix(self._pane_id(conv))
        except Exception:
            tabs.show_tab(self._pane_id(conv))

    def _set_tab_label(self, conv: str) -> None:
        try:
            tabs = self.query_one("#conversations", TabbedContent)
            content_tabs = tabs.get_child_by_type(ContentTabs)
            tab = content_tabs.get_content_tab(self._pane_id(conv))
        except Exception:
            return
        count = self._unread.get(conv, 0)
        label = self._titles.get(conv, conv)
        if count:
            label = f"{label} ({count})"
        tab.label = label

    def _bump_unread(self, conv: str) -> None:
        if conv == self._active_conv:
            return
        self._unread[conv] = self._unread.get(conv, 0) + 1
        self._set_tab_label(conv)

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        if event.pane.id is None:
            return
        conv = self._pane_conv.get(event.pane.id)
        if conv is None:
            return
        self._unread[conv] = 0
        self._set_tab_label(conv)
        self.query_one("#input-msg", Input).focus()

    # ------------------------------------------------------------------ write
    def _write_line(
        self,
        conv: str,
        author: str,
        text: str,
        style: str = "",
        stamp: str | None = None,
        ack: str = "",
    ) -> None:
        log = self._logs.get(conv)
        if log is None:
            return
        stamp = stamp or datetime.datetime.now().strftime("%H:%M:%S")
        author_part = (
            f"[{style}]{escape(author)}[/{style}]" if style else escape(author)
        )
        log.write(f"[dim]{stamp}[/dim] {author_part}: {escape(text)}{ack}")
        self._written[conv] = self._written.get(conv, 0) + 1
        self._bump_unread(conv)

    def _system_log(self, text: str, style: str = "b yellow") -> None:
        self._write_line(self._active_conv, "sistema", text, style=style)

    def _render_stored(self, conv: str, msg: Message) -> None:
        stamp = datetime.datetime.fromtimestamp(msg.ts).strftime("%H:%M:%S")
        style = "b cyan" if msg.direction == "sent" else ""
        ack = ""
        if msg.direction == "sent":
            if msg.ack_state == "ack":
                ack = " [green]✓[/green]"
            elif msg.ack_state == "nak":
                ack = " [red]✗[/red]"
            elif msg.ack_state == "pending":
                ack = " [dim]…[/dim]"
        self._write_line(
            conv, msg.author_name, msg.text, style=style, stamp=stamp, ack=ack
        )

    # -------------------------------------------------------------- conectar
    def action_connect(self) -> None:
        self.push_screen(ConnectScreen(), callback=self._start_connect)

    def _start_connect(self, choice: tuple[str, str] | None) -> None:
        if not choice:
            return
        kind, target = choice
        if kind == "tcp" and not target:
            self._set_status("Host TCP vazio.")
            return
        self._set_status(f"Conectando ({kind}: {target or 'auto'})...")
        self._connect_worker(kind, target)

    @work(thread=True, exclusive=True, group="connect")
    def _connect_worker(self, kind: str, target: str) -> None:
        try:
            self.link.connect(kind, target)
        except Exception as exc:
            self.call_from_thread(self._on_connect_error, str(exc))
        else:
            # O evento 'established' pode ser publicado antes do subscribe,
            # então sincronizamos a UI explicitamente após conectar.
            self.call_from_thread(self._on_connected)

    def _on_connect_error(self, message: str) -> None:
        self._set_status(f"Falha ao conectar: {message}")
        self._system_log(message, style="b red")

    def action_disconnect(self) -> None:
        self.link.disconnect()
        self.SUB_TITLE = "desconectado"
        self._set_status("Desconectado — pressione F2 para conectar")
        self._system_log("Desconectado.")

    # ------------------------------------------------------------------ enviar
    def _node_title(self, node_ref: int | str | None) -> str:
        return self.link.node_name(node_ref)

    def _send_target(self) -> tuple[str, str, int]:
        """Retorna (conversa, destino, canal) para o envio atual."""
        active = self._active_conv
        if active.startswith("dm:"):
            dest = "!" + active[3:]
            channel = self._dm_channel.get(active, 0)
            return active, dest, channel
        channel = int(active[3:]) if active.startswith("ch:") else 0
        dest = self._selected_destination()
        if dest != BROADCAST:
            conv = f"dm:{dest.lstrip('!')}"
            if conv not in self._titles:
                self._ensure_tab(conv, self._node_title(dest))
            self._switch_tab(conv)
            return conv, dest, 0
        return active, BROADCAST, channel

    def action_send(self) -> None:
        input_msg = self.query_one("#input-msg", Input)
        text = input_msg.value.strip()
        if not text:
            return
        conv, destination, channel = self._send_target()
        input_msg.value = ""
        my = self._my_nodenum()
        rowid = self._store.add(
            ts=time.time(),
            conv=conv,
            author_id=str(my) if my is not None else "",
            author_name="eu",
            text=text,
            direction="sent",
            ack_state="pending",
        )
        self._row_conv[rowid] = conv
        self._send_worker(text, channel, destination, rowid)
        self._write_line(conv, "eu", text, style="b cyan", ack=" [dim]…[/dim]")

    @work(thread=True, exclusive=True, group="send")
    def _send_worker(self, text: str, channel: int, destination: str, rowid: int) -> None:
        try:
            packet_id = self.link.send_text(text, channel, destination)
        except Exception as exc:
            self.call_from_thread(
                self._system_log, f"falha ao enviar: {exc}", "b red"
            )
        else:
            if packet_id is not None:
                self.call_from_thread(self._bind_ack, packet_id, rowid)

    def _bind_ack(self, packet_id: int, rowid: int) -> None:
        self._ack_rows[packet_id] = rowid

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "input-msg":
            self.action_send()

    # ------------------------------------------------------------- selects
    def _selected_destination(self) -> str:
        value = self.query_one("#dest-select", Select).value
        return str(value) if value else BROADCAST

    def _channel_name(self, index: int) -> str:
        return self._channel_labels.get(index, f"CH{index}")

    def _populate_channels(self) -> None:
        channels = self.link.channels() or [{"index": 0, "name": "CH0"}]
        self._channel_labels = {c["index"]: c["name"] for c in channels}
        for ch in channels:
            self._ensure_tab(f"ch:{ch['index']}", ch["name"])

    def _populate_destinations(self) -> None:
        select = self.query_one("#dest-select", Select)
        current = select.value
        options: list[tuple[str, str]] = [("📡 Broadcast", BROADCAST)]
        for num, node in sorted(self.link.nodes().items(), key=lambda kv: self._node_sort_key(kv[1])):
            user = node.get("user", {})
            name = user.get("longName") or user.get("shortName") or f"!{num:08x}"
            options.append((name, f"!{num:08x}"))
        select.set_options(options)
        select.value = current if current in dict(options).values() else BROADCAST

    @staticmethod
    def _node_sort_key(node: dict[str, Any]) -> tuple:
        user = node.get("user", {})
        name = (user.get("longName") or user.get("shortName") or "").lower()
        return (0 if node.get("isFavorite") else 1, name)

    # ------------------------------------------------------------------ nós
    def action_refresh_nodes(self) -> None:
        self._render_nodes()
        self._populate_destinations()
        self._set_status(f"Nós atualizados: {len(self.link.nodes())}")

    def _render_nodes(self) -> None:
        table = self.query_one("#nodes", DataTable)
        table.clear()
        for num, node in sorted(self.link.nodes().items(), key=lambda kv: self._node_sort_key(kv[1])):
            user = node.get("user", {})
            name = user.get("shortName") or user.get("longName") or f"!{num:08x}"
            table.add_row(
                name,
                self._fmt_num(node.get("snr")),
                self._fmt_hops(node.get("hopsAway")),
                self._fmt_battery(node),
                ago_desc(node.get("lastHeard")) or "-",
                key=str(num),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            num = int(str(event.row_key.value))
        except (TypeError, ValueError):
            return
        nodes = self.link.nodes()
        node = nodes.get(num)
        if node is None:
            return
        local = nodes.get(self._my_nodenum() or -1)
        self.push_screen(NodeDetailScreen(render_details(num, node, local)))

    # -------------------------------------------------------- nós novos
    def _sync_known_nodes(self, announce: bool) -> None:
        for num in self.link.nodes():
            if num in self._known_nodes:
                continue
            self._known_nodes.add(num)
            if announce and num != self._my_nodenum():
                self._announce_node(num)

    def _announce_node(self, num: int) -> None:
        name = self.link.node_name(num)
        self._system_log(f"Nó novo na rede: {name}")
        self.notify(f"{name} entrou na rede", title="Nó novo")

    @staticmethod
    def _fmt_num(value: Any, digits: int = 1) -> str:
        try:
            return f"{float(value):.{digits}f}"
        except (TypeError, ValueError):
            return "-"

    @staticmethod
    def _fmt_hops(value: Any) -> str:
        return "-" if value is None else str(value)

    @staticmethod
    def _fmt_battery(node: dict[str, Any]) -> str:
        level = (node.get("deviceMetrics") or {}).get("batteryLevel")
        return "-" if level is None else f"{level:.0f}%"

    # --------------------------------------------------------- eventos do link
    def _on_link_event(self, event: str, payload: dict[str, Any]) -> None:
        """Chamado por threads do SDK — faz marshal para a thread da UI."""
        try:
            self.call_from_thread(self._dispatch_event, event, payload)
        except RuntimeError:
            # Já estamos na thread da UI (evento síncrono).
            self.call_after_refresh(self._dispatch_event, event, payload)

    def _dispatch_event(self, event: str, payload: dict[str, Any]) -> None:
        if event == "text":
            self._on_text_packet(payload.get("packet", {}))
        elif event == "connected":
            self._on_connected()
        elif event == "disconnected":
            if self.link.connected:
                return
            self.SUB_TITLE = "desconectado"
            if self.link.reconnecting:
                self._set_status("Conexão perdida — reconectando automaticamente...")
                self._system_log("Conexão perdida. Reconectando...")
            else:
                self._set_status("Conexão perdida.")
                self._system_log("Conexão perdida.")
        elif event == "reconnect_failed":
            if self.link.connected:
                return
            self._set_status(
                f"Reconectando (tentativa {payload.get('attempt', '?')})..."
            )
            if int(payload.get("attempt") or 0) <= 3:
                self._system_log(f"Reconexão falhou: {payload.get('error', '?')}")
        elif event == "ack":
            self._on_ack(payload)
        elif event == "node":
            self._render_nodes()
            if self._nodes_synced:
                self._sync_known_nodes(announce=True)

    def _on_connected(self) -> None:
        node_name = self.link.node_name(self._my_nodenum())
        self.SUB_TITLE = f"conectado · {node_name}"
        self._populate_channels()
        self._render_nodes()
        self._populate_destinations()
        self._sync_known_nodes(announce=False)
        self._nodes_synced = True
        channels = ", ".join(
            self._channel_name(c["index"]) for c in self.link.channels()
        ) or "CH0"
        self._set_status(f"Conectado como {node_name} · canais: {channels}")
        self._system_log(f"Conectado como {node_name}.", style="b green")

    def _my_nodenum(self) -> int | None:
        iface = self.link.interface
        if iface is None:
            return None
        try:
            return iface.myInfo.my_node_num
        except Exception:
            return None

    # ------------------------------------------------------------ mensagens
    def _conv_for_packet(self, packet: dict[str, Any]) -> str:
        to = packet.get("to")
        my = self._my_nodenum()
        try:
            to_num = int(to) if to is not None else None
        except (TypeError, ValueError):
            to_num = None
        sender = packet.get("from")
        if (
            to_num is not None
            and my is not None
            and to_num == my
            and sender is not None
        ):
            return f"dm:{int(sender) & 0xffffffff:08x}"
        return f"ch:{int(packet.get('channel') or 0)}"

    def _on_text_packet(self, packet: dict[str, Any]) -> None:
        decoded = packet.get("decoded", {})
        text = decoded.get("text")
        if not text:
            return
        sender = packet.get("from")
        conv = self._conv_for_packet(packet)
        if conv.startswith("dm:"):
            self._dm_channel.setdefault(conv, int(packet.get("channel") or 0))
        if conv not in self._titles:
            title = self._node_title(sender) if conv.startswith("dm:") else conv[3:]
            self._ensure_tab(conv, title)
        author = self.link.node_name(sender)
        self._store.add(
            ts=time.time(),
            conv=conv,
            author_id=str(sender) if sender is not None else "",
            author_name=author,
            text=text,
            direction="recv",
        )
        self._write_line(conv, author, text)

    def _on_ack(self, payload: dict[str, Any]) -> None:
        packet = payload.get("packet", {})
        decoded = packet.get("decoded", {})
        routing = decoded.get("routing") or {}
        error = routing.get("errorReason") or "NONE"
        try:
            request_id = int(decoded.get("requestId"))
        except (TypeError, ValueError):
            request_id = None
        rowid = self._ack_rows.pop(request_id, None) if request_id is not None else None
        conv = self._row_conv.pop(rowid, None) if rowid is not None else None
        if conv is None:
            conv = self._active_conv
        if rowid is not None:
            self._store.set_ack(rowid, "ack" if error == "NONE" else "nak")
        sender = packet.get("from")
        if sender == self._my_nodenum():
            name = "mesh"
        else:
            name = self.link.node_name(sender)
        text = (payload.get("text") or "").strip()
        snippet = f' "{text[:40]}"' if text else ""
        if error == "NONE":
            self._write_line(conv, "ack", f"entregue para {name}{snippet}", style="green")
        else:
            self._write_line(conv, "nak", f"não entregue para {name} ({error}){snippet}", style="b red")

    # ---------------------------------------------------------------- shutdown
    def on_unmount(self) -> None:
        self.link.disconnect()
        self._store.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="mesh-tui", description="TUI para redes Meshtastic (SDK Python + Textual)."
    )
    parser.add_argument("--port", help="porta serial do rádio (ex: /dev/ttyUSB0)")
    parser.add_argument("--host", help="host TCP do nó (ex: 192.168.1.50[:4403])")
    args = parser.parse_args(argv)
    MeshTuiApp(serial_port=args.port, tcp_host=args.host).run()


if __name__ == "__main__":
    main()
