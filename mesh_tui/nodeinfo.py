"""Node information formatting: position, telemetry and details panel."""

from __future__ import annotations

import datetime
import math
from typing import Any

from rich.markup import escape

from . import i18n

COMPASS_EN = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]
COMPASS_PT = [
    "N", "NNE", "NE", "LNE", "L", "LSE", "SE", "SSE",
    "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO",
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(deg: float) -> str:
    rose = COMPASS_PT if i18n.language() == "pt" else COMPASS_EN
    return rose[int((deg + 11.25) // 22.5) % 16]


def position_coords(node: dict[str, Any] | None) -> tuple[float, float] | None:
    pos = (node or {}).get("position") or {}
    try:
        lat, lon = float(pos["latitude"]), float(pos["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if lat == 0.0 and lon == 0.0:
        return None
    return lat, lon


def distance_desc(
    node: dict[str, Any], local: dict[str, Any] | None
) -> str | None:
    here = position_coords(local)
    there = position_coords(node)
    if here is None or there is None:
        return None
    km = haversine_km(here[0], here[1], there[0], there[1])
    dist = f"{km * 1000:.0f} m" if km < 1.0 else f"{km:.1f} km"
    direction = compass(bearing_deg(here[0], here[1], there[0], there[1]))
    return i18n.t("node.distance", dist=dist, dir=direction)


def ago_desc(last_heard: Any) -> str:
    if not last_heard:
        return ""
    try:
        delta = datetime.datetime.now() - datetime.datetime.fromtimestamp(
            float(last_heard)
        )
    except (TypeError, ValueError, OSError):
        return ""
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return i18n.t("node.now")
    if seconds < 3600:
        return f"{max(seconds // 60, 0)}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def uptime_desc(seconds: Any) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, _ = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def render_details(
    num: int, node: dict[str, Any], local: dict[str, Any] | None
) -> str:
    """Render the node details panel (rich markup)."""
    user = node.get("user") or {}
    lines: list[str] = []

    title = f"[b]{escape(str(user.get('longName') or '?'))}[/b]"
    short = user.get("shortName")
    if short and short != user.get("longName"):
        title += f" [dim]({escape(str(short))})[/dim]"
    lines.append(title)

    bits = [f"!{num & 0xffffffff:08x}"]
    if user.get("role"):
        bits.append(i18n.t("node.role", value=escape(str(user["role"]))))
    if user.get("hwModel"):
        bits.append(i18n.t("node.hardware", value=escape(str(user["hwModel"]))))
    lines.append("[dim]" + " · ".join(bits) + "[/dim]")

    radio: list[str] = []
    if node.get("snr") is not None:
        radio.append(i18n.t("node.snr", value=_num(node["snr"])))
    if node.get("hopsAway") is not None:
        radio.append(i18n.t("node.hops", n=node["hopsAway"]))
    seen = ago_desc(node.get("lastHeard"))
    if seen:
        radio.append(i18n.t("node.seen", ago=seen))
    if radio:
        lines.append(" · ".join(radio))

    flags: list[str] = []
    if node.get("isFavorite"):
        flags.append(i18n.t("node.favorite"))
    if node.get("viaMqtt"):
        flags.append(i18n.t("node.via.mqtt"))
    if flags:
        lines.append("[dim]" + " · ".join(flags) + "[/dim]")

    pos = position_coords(node)
    if pos is not None:
        alt = (node.get("position") or {}).get("altitude")
        alt_s = f", {alt:.0f} m" if alt is not None else ""
        lines += [
            "",
            i18n.t("node.position", lat=f"{pos[0]:.5f}", lon=f"{pos[1]:.5f}", alt=alt_s),
        ]
        dist = distance_desc(node, local)
        if dist:
            lines.append(f"  [dim]↳ {dist}[/dim]")

    dev = node.get("deviceMetrics") or {}
    parts: list[str] = []
    if dev.get("batteryLevel") is not None:
        parts.append(i18n.t("node.battery", level=dev["batteryLevel"]))
    if dev.get("voltage") is not None:
        parts.append(i18n.t("node.voltage", value=_num(dev["voltage"], 2)))
    if dev.get("channelUtilization") is not None:
        parts.append(i18n.t("node.channel.util", value=_num(dev["channelUtilization"])))
    if dev.get("airUtilTx") is not None:
        parts.append(i18n.t("node.air.tx", value=_num(dev["airUtilTx"])))
    if dev.get("uptimeSeconds") is not None:
        parts.append(i18n.t("node.uptime", value=uptime_desc(dev["uptimeSeconds"])))
    if parts:
        lines += ["", f"[b]{i18n.t('node.device')}[/b]", "  " + " · ".join(parts)]

    env = node.get("environmentMetrics") or {}
    parts = []
    if env.get("temperature") is not None:
        parts.append(i18n.t("node.temp", value=_num(env["temperature"])))
    if env.get("relativeHumidity") is not None:
        parts.append(i18n.t("node.humidity", value=env["relativeHumidity"]))
    if env.get("barometricPressure") is not None:
        parts.append(i18n.t("node.pressure", value=_num(env["barometricPressure"], 0)))
    if parts:
        lines += ["", f"[b]{i18n.t('node.environment')}[/b]", "  " + " · ".join(parts)]

    return "\n".join(lines)
