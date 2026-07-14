"""Data structures shared by the log parser, store, and terminal UI."""

from dataclasses import dataclass
from datetime import datetime


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
    backend_tx_bytes: int
    backend_rx_bytes: int
    request_length: int
    bytes_sent: int
    latency_ms: int


@dataclass(frozen=True)
class FrontendSummary:
    """Rolling upstream traffic metrics for one frontend virtual host."""

    frontend_url: str
    request_count: int
    backend_tx_bytes: int
    backend_rx_bytes: int
    backend_tx_rate: float
    backend_rx_rate: float
