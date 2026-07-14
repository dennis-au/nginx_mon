"""In-memory request retention and per-frontend rolling summaries."""

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, List, Optional

from .models import FrontendSummary, RequestRecord


class TrafficStore:
    """Store a bounded request history and summarize its current traffic."""

    def __init__(self, max_records: int = 5_000, rate_window_seconds: int = 60):
        if max_records < 1:
            raise ValueError("max_records must be positive")
        if rate_window_seconds < 1:
            raise ValueError("rate_window_seconds must be positive")
        self._records: Deque[RequestRecord] = deque(maxlen=max_records)
        self.rate_window_seconds = rate_window_seconds

    def add(self, record: RequestRecord) -> None:
        self._records.append(record)

    def requests_for(self, frontend_url: str) -> List[RequestRecord]:
        return [record for record in self._records if record.frontend_url == frontend_url]

    def summaries(self, now: Optional[datetime] = None) -> List[FrontendSummary]:
        current_time = now or datetime.now(timezone.utc)
        cutoff = current_time - timedelta(seconds=self.rate_window_seconds)
        groups: Dict[str, List[RequestRecord]] = {}
        for record in self._records:
            if record.timestamp >= cutoff:
                groups.setdefault(record.frontend_url, []).append(record)

        summaries = []
        for frontend_url, records in groups.items():
            tx_bytes = sum(record.backend_tx_bytes for record in records)
            rx_bytes = sum(record.backend_rx_bytes for record in records)
            earliest = min(record.timestamp for record in records)
            observed_seconds = max(1.0, (current_time - earliest).total_seconds())
            observed_seconds = min(observed_seconds, float(self.rate_window_seconds))
            summaries.append(
                FrontendSummary(
                    frontend_url=frontend_url,
                    request_count=len(records),
                    backend_tx_bytes=tx_bytes,
                    backend_rx_bytes=rx_bytes,
                    backend_tx_rate=tx_bytes / observed_seconds,
                    backend_rx_rate=rx_bytes / observed_seconds,
                    source_endpoints=tuple(
                        sorted({record.source_endpoint for record in records})
                    ),
                    network_connections=tuple(
                        sorted(
                            {
                                record.network_connection
                                for record in records
                                if record.network_connection and record.network_connection != "-"
                            }
                        )
                    ),
                    backend_endpoints=tuple(
                        sorted({record.backend_endpoint for record in records})
                    ),
                    tls_protocols=tuple(
                        sorted({record.ssl_protocol for record in records if record.ssl_protocol})
                    ),
                )
            )
        return sorted(
            summaries,
            key=lambda item: (item.backend_tx_bytes + item.backend_rx_bytes, item.frontend_url),
            reverse=True,
        )
