import json
from datetime import datetime, timezone

from nginx_mon.parser import NginxJsonParser, parse_nginx_bytes, parse_upstream_endpoint


def test_parser_builds_a_request_record_from_nginx_json():
    line = json.dumps(
        {
            "time": "2026-07-14T12:34:56+00:00",
            "scheme": "https",
            "host": "api.example.test",
            "server_port": "443",
            "server_addr": "192.0.2.20",
            "source_addr": "203.0.113.42",
            "source_port": "53214",
            "ssl_protocol": "TLSv1.3",
            "request": "GET /v1/widgets?limit=10 HTTP/1.1",
            "method": "GET",
            "uri": "/v1/widgets?limit=10",
            "status": "200",
            "upstream_addr": "10.0.0.10:8080",
            "request_length": "321",
            "bytes_sent": "2048",
            "upstream_bytes_sent": "128, 64",
            "upstream_bytes_received": "4096",
            "request_time": "0.125",
            "upstream_response_time": "0.050, 0.075",
        }
    )

    record = NginxJsonParser().parse_line(line)

    assert record is not None
    assert record.frontend_url == "https://api.example.test:443"
    assert record.source_ip == "203.0.113.42"
    assert record.source_port == "53214"
    assert record.listener_ip == "192.0.2.20"
    assert record.frontend_port == "443"
    assert record.ssl_protocol == "TLSv1.3"
    assert record.method == "GET"
    assert record.uri == "/v1/widgets?limit=10"
    assert record.status == 200
    assert record.upstream_address == "10.0.0.10:8080"
    assert record.backend_ip == "10.0.0.10"
    assert record.backend_port == "8080"
    assert record.backend_tx_bytes == 192
    assert record.backend_rx_bytes == 4096
    assert record.request_length == 321
    assert record.bytes_sent == 2048
    assert record.latency_ms == 125
    assert record.timestamp == datetime(2026, 7, 14, 12, 34, 56, tzinfo=timezone.utc)


def test_parser_treats_absent_upstream_values_as_zero():
    line = json.dumps(
        {
            "time": "2026-07-14T12:34:56+00:00",
            "host": "example.test",
            "request": "GET / HTTP/1.1",
            "method": "GET",
            "uri": "/",
            "status": "404",
            "upstream_addr": "-",
            "upstream_bytes_sent": "-",
            "upstream_bytes_received": "",
            "request_time": "-",
        }
    )

    record = NginxJsonParser().parse_line(line)

    assert record is not None
    assert record.frontend_url == "http://example.test:80"
    assert record.source_ip == "-"
    assert record.source_port == "-"
    assert record.listener_ip == "-"
    assert record.frontend_port == "80"
    assert record.ssl_protocol == ""
    assert record.backend_tx_bytes == 0
    assert record.backend_rx_bytes == 0
    assert record.latency_ms == 0
    assert record.upstream_address == "-"


def test_parser_discards_malformed_or_incomplete_lines():
    parser = NginxJsonParser()

    assert parser.parse_line("not json") is None
    assert parser.parse_line(json.dumps({"host": "example.test"})) is None


def test_parse_nginx_bytes_sums_multiple_upstream_attempts():
    assert parse_nginx_bytes("1024, 512, -") == 1536
    assert parse_nginx_bytes(None) == 0


def test_parse_upstream_endpoint_handles_ipv6_and_upstream_retry_lists():
    assert parse_upstream_endpoint("10.0.0.10:8080, [2001:db8::10]:8443") == (
        "2001:db8::10",
        "8443",
    )
    assert parse_upstream_endpoint("unix:/run/backend.sock") == ("unix:/run/backend.sock", "")
