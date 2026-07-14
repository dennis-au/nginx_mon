import asyncio
from pathlib import Path

from textual.widgets import DataTable

from nginx_mon.app import MonitorApp
from nginx_mon.models import RequestRecord


def test_monitor_displays_frontend_traffic_and_opens_request_detail():
    async def exercise_app():
        app = MonitorApp(log_file=Path("/does/not/exist"), refresh_interval=60)
        app.store.add(
            RequestRecord(
                timestamp=app.now(),
                frontend_url="https://api.example.test",
                method="GET",
                uri="/v1/widgets",
                request="GET /v1/widgets HTTP/1.1",
                status=200,
                upstream_address="10.0.0.10:8080",
                source_ip="203.0.113.42",
                source_port="53214",
                listener_ip="192.0.2.20",
                frontend_port="443",
                ssl_protocol="TLSv1.3",
                network_connection="ens18",
                backend_ip="10.0.0.10",
                backend_port="8080",
                backend_tx_bytes=120,
                backend_rx_bytes=4096,
                request_length=200,
                bytes_sent=4200,
                latency_ms=32,
            )
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one("#traffic-table", DataTable)
            assert table.row_count == 1
            labels = [column.label.plain for column in table.columns.values()]
            assert "Frontend URL" in labels
            assert "TLS" in labels
            assert "Sources" in labels
            assert "Network" in labels
            assert "Backends" in labels

            await pilot.press("enter")
            await pilot.pause()
            detail_table = app.query_one("#request-table", DataTable)
            assert detail_table.row_count == 1
            assert "Source" in [column.label.plain for column in detail_table.columns.values()]
            assert "Network" in [column.label.plain for column in detail_table.columns.values()]

    asyncio.run(exercise_app())


def test_monitor_skips_table_refresh_while_detail_screen_is_active():
    async def exercise_app():
        app = MonitorApp(log_file=Path("/does/not/exist"), refresh_interval=60)
        app.store.add(
            RequestRecord(
                timestamp=app.now(),
                frontend_url="https://api.example.test",
                method="GET",
                uri="/v1/widgets",
                request="GET /v1/widgets HTTP/1.1",
                status=200,
                upstream_address="10.0.0.10:8080",
                source_ip="203.0.113.42",
                source_port="53214",
                listener_ip="192.0.2.20",
                frontend_port="443",
                ssl_protocol="TLSv1.3",
                network_connection="ens18",
                backend_ip="10.0.0.10",
                backend_port="8080",
                backend_tx_bytes=120,
                backend_rx_bytes=4096,
                request_length=200,
                bytes_sent=4200,
                latency_ms=32,
            )
        )

        async with app.run_test() as pilot:
            await pilot.press("enter")
            app.refresh_data()
            assert app.query_one("#request-table", DataTable).row_count == 1
            await pilot.press("p")
            assert app.is_paused

    asyncio.run(exercise_app())


def test_monitor_uses_monokai_hides_screenshot_and_pauses_refresh(tmp_path):
    async def exercise_app():
        log_file = tmp_path / "access.json.log"
        log_file.write_text("", encoding="utf-8")
        app = MonitorApp(log_file=log_file, refresh_interval=60)

        async with app.run_test() as pilot:
            assert app.theme == "monokai"
            assert "Save screenshot" not in [
                command.title for command in app.get_system_commands(app.screen)
            ]

            await pilot.press("p")
            assert app.is_paused
            assert "Paused" in app.query_one("#status").renderable

            timestamp = app.now().isoformat()
            log_file.write_text(
                '{{"time":"{}","host":"api.example.test",'
                '"request":"GET / HTTP/1.1","method":"GET","uri":"/"}}\n'.format(
                    timestamp
                ),
                encoding="utf-8",
            )
            app.refresh_data()
            assert app.query_one("#traffic-table", DataTable).row_count == 0

            await pilot.press("p")
            assert not app.is_paused
            app.refresh_data()
            assert app.query_one("#traffic-table", DataTable).row_count == 1

    asyncio.run(exercise_app())
