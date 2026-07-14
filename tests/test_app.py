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
            assert "Frontend URL" in [column.label.plain for column in table.columns.values()]

            await pilot.press("enter")
            await pilot.pause()
            detail_table = app.query_one("#request-table", DataTable)
            assert detail_table.row_count == 1

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

    asyncio.run(exercise_app())
