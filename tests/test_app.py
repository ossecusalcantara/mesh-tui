"""Headless tests (Textual run_test) with a simulated Meshtastic interface."""

from __future__ import annotations

import asyncio
import tempfile
import threading
import types
from pathlib import Path

from serial import SerialException
from textual.widgets import DataTable, Input, Select

import meshtastic.serial_interface
import mesh_tui.i18n as i18n
import mesh_tui.meshtastic_link as mlink
import mesh_tui.nodeinfo as nodeinfo
from mesh_tui.app import MeshTuiApp, NodeDetailScreen
from mesh_tui.storage import MessageStore


class FakeIface:
    def __init__(self) -> None:
        self.failure = None
        self.isConnected = threading.Event()
        self.isConnected.set()
        self.myInfo = type("M", (), {"my_node_num": 1234})()
        self.nodesByNum = {
            1234: {
                "user": {"shortName": "EU", "longName": "Node Local"},
                "snr": 12.3,
                "position": {
                    "latitude": -23.5505, "longitude": -46.6333, "altitude": 742,
                },
            },
            999: {
                "user": {"shortName": "N2", "longName": "Node Dois"},
                "snr": -7.5,
                "hopsAway": 2,
                "lastHeard": 1770000000,
                "position": {
                    "latitude": -23.5535, "longitude": -46.6250, "altitude": 750,
                },
                "deviceMetrics": {
                    "batteryLevel": 81, "voltage": 4.12,
                    "channelUtilization": 12.3, "airUtilTx": 3.4,
                    "uptimeSeconds": 93720,
                },
                "environmentMetrics": {
                    "temperature": 25.4, "relativeHumidity": 60,
                    "barometricPressure": 1013.2,
                },
            },
        }

        class LN:
            channels = [
                type(
                    "C",
                    (),
                    {
                        "index": 0,
                        "role": "PRIMARY",
                        "settings": type("S", (), {"name": "LongFast"})(),
                    },
                )()
            ]

        self.localNode = LN()
        self.sent: list[dict] = []
        self._next_id = 100

    def sendText(self, **kw):
        self.sent.append(kw)
        self._next_id += 1
        return types.SimpleNamespace(id=self._next_id)

    def close(self) -> None:
        pass


async def wait_until(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return predicate()


def drop_connection(app: MeshTuiApp, iface: FakeIface) -> None:
    """Mimic the real SDK: clears isConnected and publishes conn.lost."""
    iface.isConnected.clear()
    threading.Thread(
        target=lambda: app.link._on_conn_lost(interface=iface)
    ).start()


def test_describe_error() -> None:
    assert "dialout" in mlink.describe_error(
        PermissionError("[Errno 13] Permission denied")
    )
    assert "multiple serial ports" in mlink.describe_error(SystemExit(1))
    assert "not found" in mlink.describe_error(
        SerialException("could not open port '/dev/ttyX': [Errno 2] No such file or directory")
    )
    assert "busy" in mlink.describe_error(
        SerialException("could not open port '/dev/ttyUSB0': [Errno 16] Device or resource busy")
    )
    assert "refused" in mlink.describe_error(ConnectionRefusedError(111, "Connection refused"))
    print("DESCRIBE_ERROR OK")


def test_connect_error_friendly() -> None:
    real = meshtastic.serial_interface.SerialInterface

    def denied(**kw):
        raise PermissionError("[Errno 13] Permission denied: '/dev/ttyUSB0'")

    meshtastic.serial_interface.SerialInterface = denied
    try:
        link = mlink.MeshtasticLink()
        try:
            link.connect("serial", "/dev/ttyUSB0")
        except ConnectionError as exc:
            assert "dialout" in str(exc), str(exc)
        else:
            raise AssertionError("connect deveria ter falhado")
        assert not link.connected
        assert not link.reconnecting
    finally:
        meshtastic.serial_interface.SerialInterface = real
    print("CONNECT_ERROR OK")


def test_store() -> None:
    path = Path(tempfile.mkdtemp()) / "history.db"
    store = MessageStore(path)
    r1 = store.add(1000.0, "ch:0", "1234", "eu", "a", "sent", ack_state="pending")
    store.add(1001.0, "ch:0", "999", "N2", "b", "recv")
    store.add(1002.0, "dm:000003e7", "999", "N2", "dm", "recv")
    msgs = store.recent("ch:0")
    assert [m.text for m in msgs] == ["a", "b"]
    assert msgs[0].rowid == r1 and msgs[0].ack_state == "pending"
    store.set_ack(r1, "ack")
    assert store.recent("ch:0")[0].ack_state == "ack"
    assert [m.text for m in store.recent("dm:000003e7")] == ["dm"]
    store.close()
    store2 = MessageStore(path)
    assert len(store2.recent("ch:0")) == 2
    store2.close()
    print("STORE OK")


def test_nodeinfo() -> None:
    i18n.set_language("en")
    assert nodeinfo.haversine_km(0, 0, 0, 0) == 0.0
    assert abs(nodeinfo.haversine_km(0, 0, 1, 0) - 111.19) < 0.5
    assert nodeinfo.compass(0) == "N"
    assert nodeinfo.compass(45) == "NE"
    assert nodeinfo.compass(90) == "E"
    assert nodeinfo.compass(180) == "S"
    assert nodeinfo.compass(270) == "W"
    assert nodeinfo.bearing_deg(0, 0, 1, 0) == 0
    assert abs(nodeinfo.bearing_deg(0, 0, 0, 1) - 90) < 0.01
    assert nodeinfo.uptime_desc(93720) == "1d 2h"
    assert nodeinfo.position_coords({}) is None
    assert nodeinfo.position_coords({"position": {"latitude": 0, "longitude": 0}}) is None

    local = {"position": {"latitude": -23.5505, "longitude": -46.6333}}
    remote = {"position": {"latitude": -23.5535, "longitude": -46.6250}}
    dist = nodeinfo.distance_desc(remote, local)
    assert dist is not None and "from local node" in dist, dist
    assert nodeinfo.distance_desc(remote, None) is None

    node = {
        "user": {"shortName": "N2", "longName": "Node Dois", "role": "CLIENT",
                 "hwModel": "TBEAM"},
        "snr": -7.5, "hopsAway": 2, "lastHeard": 1770000000,
        "isFavorite": True,
        "position": {"latitude": -23.5535, "longitude": -46.6250, "altitude": 750},
        "deviceMetrics": {"batteryLevel": 81, "voltage": 4.12,
                          "channelUtilization": 12.3, "airUtilTx": 3.4,
                          "uptimeSeconds": 93720},
        "environmentMetrics": {"temperature": 25.4, "relativeHumidity": 60,
                               "barometricPressure": 1013.2},
    }
    markup = nodeinfo.render_details(999, node, local)
    assert "Node Dois" in markup
    assert "!000003e7" in markup
    assert "CLIENT" in markup and "TBEAM" in markup
    assert "battery 81%" in markup and "4.12 V" in markup
    assert "channel use 12.3%" in markup and "TX air 3.4%" in markup
    assert "1d 2h" in markup
    assert "25.4 °C" in markup and "60% RH" in markup
    assert "Position" in markup and "↳" in markup
    assert "favorite" in markup
    print("NODEINFO OK")


def test_i18n() -> None:
    i18n.set_language("en")
    assert i18n.t("key.connect") == "Connect"
    assert nodeinfo.compass(90) == "E"

    i18n.set_language("pt")
    assert i18n.t("key.connect") == "Conectar"
    assert i18n.t("err.multiple.ports").startswith("múltiplas")
    assert nodeinfo.compass(90) == "L"

    local = {"position": {"latitude": -23.5505, "longitude": -46.6333}}
    remote = {"position": {"latitude": -23.5535, "longitude": -46.6250}}
    dist = nodeinfo.distance_desc(remote, local)
    assert dist is not None and "do nó local" in dist, dist

    node = {"user": {"shortName": "N2", "longName": "Node Dois"},
            "position": {"latitude": -23.5535, "longitude": -46.6250, "altitude": 750},
            "deviceMetrics": {"batteryLevel": 81, "voltage": 4.12},
            "environmentMetrics": {"temperature": 25.4}}
    markup = nodeinfo.render_details(999, node, local)
    assert "bateria 81%" in markup and "25.4 °C" in markup
    assert "Posição" in markup

    try:
        i18n.set_language("xx")
    except ValueError:
        pass
    else:
        raise AssertionError("set_language should reject unknown languages")
    assert i18n.language() == "pt"

    i18n.set_language("en")
    print("I18N OK")


async def run() -> None:
    fake = FakeIface()
    real_serial = meshtastic.serial_interface.SerialInterface
    real_delay = mlink.RECONNECT_MIN_DELAY
    meshtastic.serial_interface.SerialInterface = lambda **kw: fake
    mlink.RECONNECT_MIN_DELAY = 0.05
    events: list[tuple[str, dict]] = []
    count_failures = lambda: sum(1 for e, _ in events if e == "reconnect_failed")
    db_path = Path(tempfile.mkdtemp()) / "history.db"
    store = MessageStore(db_path)

    try:
        app = MeshTuiApp(store=store)
        async with app.run_test() as pilot:
            app.link.add_listener(lambda e, p: events.append((e, p)))

            # 1. conexão cria aba do canal com nome real
            app._start_connect(("serial", "/dev/fake"))
            assert await wait_until(lambda: app.link.interface is fake), "connect não rodou"
            await pilot.pause()
            assert app.SUB_TITLE == "connected · EU", app.SUB_TITLE
            assert await wait_until(lambda: app._titles.get("ch:0") == "LongFast")

            # 2. envio broadcast persiste com ack pendente
            app.query_one("#input-msg").value = "ola [mesh]"
            await pilot.press("ctrl+s")
            await wait_until(lambda: fake.sent)
            sent = fake.sent[0]
            assert sent["text"] == "ola [mesh]"
            assert sent["destinationId"] == "^all"
            assert sent["channelIndex"] == 0
            assert sent["wantAck"] is True
            assert sent["onResponse"].__name__ == "onAckNak"
            rows = store.recent("ch:0")
            assert rows[-1].text == "ola [mesh]"
            assert rows[-1].direction == "sent"
            assert rows[-1].ack_state == "pending"

            # 3. ACK atualiza o registro persistido
            threading.Thread(
                target=lambda: sent["onResponse"](
                    {"from": 999, "decoded": {"requestId": 101, "routing": {"errorReason": "NONE"}}}
                )
            ).start()
            assert await wait_until(
                lambda: store.recent("ch:0")[-1].ack_state == "ack"
            ), "ack não persistido"

            # 4. NAK marca falha
            app.query_one("#input-msg").value = "falha"
            await pilot.press("ctrl+s")
            await wait_until(lambda: len(fake.sent) == 2)
            fake.sent[1]["onResponse"](
                {"from": 999, "decoded": {"requestId": 102, "routing": {"errorReason": "NO_ROUTE"}}}
            )
            assert await wait_until(
                lambda: store.recent("ch:0")[-1].ack_state == "nak"
            ), "nak não persistido"

            # 5. broadcast recebido persiste
            threading.Thread(
                target=lambda: app.link._on_text(
                    packet={"from": 999, "to": 0xFFFFFFFF, "channel": 0,
                            "decoded": {"text": "oi [de] n2"}},
                    interface=fake,
                )
            ).start()
            assert await wait_until(
                lambda: any(m.text == "oi [de] n2" for m in store.recent("ch:0"))
            )

            # 6. DM recebida cria aba própria com unread
            dm = "dm:000003e7"
            threading.Thread(
                target=lambda: app.link._on_text(
                    packet={"from": 999, "to": 1234, "channel": 0,
                            "decoded": {"text": "oi dm"}},
                    interface=fake,
                )
            ).start()
            assert await wait_until(lambda: dm in app._titles), "aba de DM não criada"
            assert await wait_until(lambda: app._unread.get(dm, 0) >= 1)
            assert store.recent(dm)[-1].text == "oi dm"
            assert store.recent(dm)[-1].direction == "recv"

            # 7. ativar a aba limpa o unread
            app._switch_tab(dm)
            assert await wait_until(lambda: app._unread.get(dm) == 0)
            await pilot.pause()

            # 8. enviar a partir da aba de DM mira o nó
            app.query_one("#input-msg").value = "resposta dm"
            await pilot.press("ctrl+s")
            await wait_until(lambda: len(fake.sent) == 3)
            assert fake.sent[2]["destinationId"] == "!000003e7"
            assert fake.sent[2]["channelIndex"] == 0
            assert store.recent(dm)[-1].text == "resposta dm"

            # 9. dest-select numa aba de canal cria/switcha a DM
            app._switch_tab("ch:0")
            await pilot.pause()
            app.query_one("#dest-select", Select).value = "!000003e7"
            app.query_one("#input-msg").value = "via select"
            await pilot.press("ctrl+s")
            await wait_until(lambda: len(fake.sent) == 4)
            assert fake.sent[3]["destinationId"] == "!000003e7"
            assert app._active_conv == dm

            # 10. tabela de nós populada
            assert await wait_until(lambda: app.query_one(DataTable).row_count == 2)

            # 10b. pacotes de posição/telemetria disparam evento node
            node_events = lambda: sum(1 for e, _ in events if e == "node")
            before_nodes = node_events()
            app.link._on_node_packet(packet={"from": 999}, interface=fake)
            app.link._on_node_packet(packet={"from": 999}, interface=fake)
            assert await wait_until(lambda: node_events() >= before_nodes + 2)

            # 10c. enter na tabela abre painel de detalhes do nó
            table = app.query_one(DataTable)
            table.focus()
            table.move_cursor(row=1)
            await pilot.pause()
            await pilot.press("enter")
            assert isinstance(app.screen, NodeDetailScreen), type(app.screen)
            markup = app.screen._markup
            assert "Node Dois" in markup, markup
            assert "battery 81%" in markup and "25.4 °C" in markup
            assert "Position" in markup and "↳" in markup
            await pilot.press("escape")
            assert await wait_until(
                lambda: not isinstance(app.screen, NodeDetailScreen)
            )

            # 10d. nó novo é anunciado; nó existente não
            announced: list[int] = []
            app._announce_node = lambda num: announced.append(num)
            fake.nodesByNum[555] = {"user": {"shortName": "N3", "longName": "Node Três"}}
            app.link._on_node_updated(node=fake.nodesByNum[555], interface=fake)
            assert await wait_until(lambda: announced == [555])
            app.link._on_node_updated(node=fake.nodesByNum[999], interface=fake)
            await asyncio.sleep(0.2)
            assert announced == [555], announced

            # 10e. F7 toggles the UI language live
            await pilot.press("f7")
            await pilot.pause()
            assert i18n.language() == "pt"
            assert app.SUB_TITLE == "conectado · EU", app.SUB_TITLE
            assert app.query_one("#dest-select", Select).prompt == "Destino"
            assert app.query_one("#input-msg", Input).placeholder.startswith("Mensagem")
            table = app.query_one(DataTable)
            labels = [str(c.label) for c in table.columns.values()]
            assert "Nó" in labels and "Bateria" in labels, labels
            await pilot.press("f7")
            await pilot.pause()
            assert i18n.language() == "en"
            assert app.SUB_TITLE == "connected · EU", app.SUB_TITLE
            labels = [str(c.label) for c in table.columns.values()]
            assert "Node" in labels and "Battery" in labels, labels

            # 11. queda de conexão reconecta automaticamente
            fake2 = FakeIface()
            meshtastic.serial_interface.SerialInterface = lambda **kw: fake2
            drop_connection(app, fake)
            assert await wait_until(lambda: any(e == "connected" for e, _ in events))
            assert await wait_until(lambda: app.link.interface is fake2)

            # 12. falhas com backoff e depois sucesso
            fake3 = FakeIface()
            attempts = {"n": 0}

            def flaky(**kw):
                attempts["n"] += 1
                if attempts["n"] < 3:
                    raise PermissionError("[Errno 13] Permission denied: '/dev/ttyUSB0'")
                return fake3

            meshtastic.serial_interface.SerialInterface = flaky
            drop_connection(app, fake2)
            assert await wait_until(lambda: app.link.interface is fake3)
            failures = [p for e, p in events if e == "reconnect_failed"]
            assert len(failures) >= 2
            assert "dialout" in failures[0]["error"], failures[0]["error"]

            # 13. desconexão manual cancela a reconexão automática
            def always_fail(**kw):
                raise PermissionError("Permission denied")

            meshtastic.serial_interface.SerialInterface = always_fail
            drop_connection(app, fake3)
            assert await wait_until(lambda: count_failures() >= 1)
            app.action_disconnect()
            await asyncio.sleep(0.3)
            baseline = count_failures()
            await asyncio.sleep(0.4)
            assert count_failures() == baseline, "retries continuaram após disconnect"
            assert not app.link.reconnecting
            assert not app.link.connected
            assert app.SUB_TITLE == "disconnected"

        # 14. histórico sobrevive a reinício da aplicação
        store2 = MessageStore(db_path)
        app2 = MeshTuiApp(store=store2)
        async with app2.run_test() as pilot2:
            assert await wait_until(lambda: app2._written.get("ch:0", 0) >= 4)
            texts = [m.text for m in store2.recent("ch:0")]
            assert "ola [mesh]" in texts and "oi [de] n2" in texts
            dms = [m.text for m in store2.recent(dm)]
            assert dms == ["oi dm", "resposta dm", "via select"]

        print("TESTES OK")
    finally:
        meshtastic.serial_interface.SerialInterface = real_serial
        mlink.RECONNECT_MIN_DELAY = real_delay


if __name__ == "__main__":
    i18n.set_language("en")
    test_describe_error()
    test_connect_error_friendly()
    test_store()
    test_nodeinfo()
    test_i18n()
    asyncio.run(run())
