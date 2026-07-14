"""Parsing for the JSON Nginx access-log format documented by this project."""

import json
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Tuple

from .models import RequestRecord


def parse_nginx_bytes(value: Any) -> int:
    """Return the total for an Nginx upstream byte field.

    Nginx emits a comma-separated value when a request has more than one
    upstream attempt. Missing values are represented by ``-``.
    """

    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))

    total = 0
    for item in str(value).split(","):
        item = item.strip()
        if not item or item == "-":
            continue
        try:
            total += max(0, int(float(item)))
        except ValueError:
            continue
    return total


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return default if text == "-" else text


def _integer(value: Any) -> int:
    try:
        return max(0, int(float(_text(value, "0"))))
    except ValueError:
        return 0


def parse_upstream_endpoint(value: Any) -> Tuple[str, str]:
    """Return the final upstream host and port from an Nginx address field."""

    candidates = [
        item.strip()
        for item in _text(value).split(",")
        if item.strip() not in ("", "-")
    ]
    if not candidates:
        return "-", "-"
    address = candidates[-1]
    if address.startswith("unix:"):
        return address, ""
    if address.startswith("["):
        host, separator, port = address[1:].partition("]:")
        if separator:
            return host, port
        return address, ""
    host, separator, port = address.rpartition(":")
    if separator and host:
        return host, port
    return address, ""


def _duration_ms(value: Any) -> int:
    total_seconds = 0.0
    for item in _text(value).split(","):
        item = item.strip()
        if not item or item == "-":
            continue
        try:
            total_seconds += max(0.0, float(item))
        except ValueError:
            continue
    return int(round(total_seconds * 1000))


def _timestamp(value: Any) -> Optional[datetime]:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class NginxJsonParser:
    """Convert one documented Nginx JSON log line to a request record."""

    def parse_line(self, line: str) -> Optional[RequestRecord]:
        try:
            payload = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, Mapping):
            return None

        timestamp = _timestamp(payload.get("time"))
        host = _text(payload.get("host"))
        request = _text(payload.get("request"))
        if timestamp is None or not host or not request:
            return None

        parts = request.split()
        method = _text(payload.get("method"), parts[0] if parts else "")
        uri = _text(payload.get("uri"), parts[1] if len(parts) > 1 else "")
        if not method or not uri:
            return None

        scheme = _text(payload.get("scheme"), "http")
        frontend_port = _text(payload.get("server_port"), "443" if scheme == "https" else "80")
        upstream_address = _text(payload.get("upstream_addr"), "-")
        backend_ip, backend_port = parse_upstream_endpoint(upstream_address)
        return RequestRecord(
            timestamp=timestamp,
            frontend_url="{}://{}:{}".format(scheme, host, frontend_port),
            method=method,
            uri=uri,
            request=request,
            status=_integer(payload.get("status")),
            upstream_address=upstream_address,
            source_ip=_text(payload.get("source_addr"), "-"),
            source_port=_text(payload.get("source_port"), "-"),
            listener_ip=_text(payload.get("server_addr"), "-"),
            frontend_port=frontend_port,
            ssl_protocol=_text(payload.get("ssl_protocol")),
            network_connection="-",
            backend_ip=backend_ip,
            backend_port=backend_port,
            backend_tx_bytes=parse_nginx_bytes(payload.get("upstream_bytes_sent")),
            backend_rx_bytes=parse_nginx_bytes(payload.get("upstream_bytes_received")),
            request_length=_integer(payload.get("request_length")),
            bytes_sent=_integer(payload.get("bytes_sent")),
            latency_ms=_duration_ms(payload.get("request_time")),
        )
