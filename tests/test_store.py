from datetime import datetime, timedelta, timezone

import pytest

from nginx_mon.models import RequestRecord
from nginx_mon.store import TrafficStore


def request(frontend_url, timestamp, tx_bytes, rx_bytes, uri="/"):
    return RequestRecord(
        timestamp=timestamp,
        frontend_url=frontend_url,
        method="GET",
        uri=uri,
        request="GET {} HTTP/1.1".format(uri),
        status=200,
        upstream_address="127.0.0.1:8080",
        source_ip="192.0.2.10",
        source_port="53000",
        frontend_port="443",
        ssl_protocol="TLSv1.3",
        backend_ip="127.0.0.1",
        backend_port="8080",
        backend_tx_bytes=tx_bytes,
        backend_rx_bytes=rx_bytes,
        request_length=100,
        bytes_sent=rx_bytes,
        latency_ms=20,
    )


def test_store_aggregates_frontend_backend_rates_over_observed_window():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    store = TrafficStore(max_records=10, rate_window_seconds=60)
    store.add(request("https://api.example.test", now - timedelta(seconds=5), 100, 200))
    store.add(request("https://api.example.test", now - timedelta(seconds=1), 200, 300))

    summaries = store.summaries(now)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.frontend_url == "https://api.example.test"
    assert summary.request_count == 2
    assert summary.backend_tx_bytes == 300
    assert summary.backend_rx_bytes == 500
    assert summary.backend_tx_rate == pytest.approx(60)
    assert summary.backend_rx_rate == pytest.approx(100)
    assert summary.source_endpoints == ("192.0.2.10:53000",)
    assert summary.backend_endpoints == ("127.0.0.1:8080",)
    assert summary.tls_protocols == ("TLSv1.3",)


def test_store_keeps_only_the_configured_recent_request_history():
    now = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    store = TrafficStore(max_records=2)
    store.add(request("http://example.test", now, 1, 1, "/first"))
    store.add(request("http://example.test", now, 1, 1, "/second"))
    store.add(request("http://example.test", now, 1, 1, "/third"))

    assert [item.uri for item in store.requests_for("http://example.test")] == [
        "/second",
        "/third",
    ]
