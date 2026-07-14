"""Data structures shared by the log parser, store, and terminal UI."""

from dataclasses import dataclass
from datetime import datetime
from typing import Tuple


def format_endpoint(address: str, port: str) -> str:
    """Return a display-safe endpoint from an address and optional port."""

    if not address or address == "-":
        return "-"
    if not port or port == "-":
        return address
    if ":" in address and not address.startswith("unix:"):
        return "[{}]:{}".format(address, port)
    return "{}:{}".format(address, port)


@dataclass(frozen=True)
class RequestRecord:
    """One completed reverse-proxy request from the Nginx access log."""

    timestamp: datetime
    frontend_url: str
    method: str
    uri: str
    request: str
    status: int
    upstream_address: str
    source_ip: str
    source_port: str
    listener_ip: str
    frontend_port: str
    ssl_protocol: str
    network_connection: str
    backend_ip: str
    backend_port: str
    backend_tx_bytes: int
    backend_rx_bytes: int
    request_length: int
    bytes_sent: int
    latency_ms: int

    @property
    def source_endpoint(self) -> str:
        return format_endpoint(self.source_ip, self.source_port)

    @property
    def backend_endpoint(self) -> str:
        return format_endpoint(self.backend_ip, self.backend_port)

    @property
    def listener_endpoint(self) -> str:
        if not self.listener_ip or self.listener_ip == "-":
            return "port {}".format(self.frontend_port)
        return format_endpoint(self.listener_ip, self.frontend_port)


@dataclass(frozen=True)
class FrontendSummary:
    """Rolling upstream traffic metrics for one frontend virtual host."""

    frontend_url: str
    request_count: int
    backend_tx_bytes: int
    backend_rx_bytes: int
    backend_tx_rate: float
    backend_rx_rate: float
    source_endpoints: Tuple[str, ...]
    network_connections: Tuple[str, ...]
    backend_endpoints: Tuple[str, ...]
    tls_protocols: Tuple[str, ...]
