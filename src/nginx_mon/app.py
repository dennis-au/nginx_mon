"""Textual screens for the live Nginx traffic monitor."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from .models import FrontendSummary, RequestRecord
from .parser import NginxJsonParser
from .store import TrafficStore
from .tailer import LogFollower


def format_bytes(value: float) -> str:
    """Display a byte count using compact binary units."""

    units = ("B", "KiB", "MiB", "GiB", "TiB")
    size = float(value)
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            if unit == "B":
                return "{:.0f} {}".format(size, unit)
            return "{:.1f} {}".format(size, unit)
        size /= 1024
    return "{:.1f} TiB".format(size)


class RequestDetailScreen(Screen[None]):
    """Display retained requests for one frontend URL."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("q", "quit_monitor", "Quit"),
    ]

    CSS = """
    #detail-title {
        height: 1;
        padding: 0 1;
        background: $boost;
    }

    #request-table {
        height: 1fr;
    }
    """

    def __init__(self, frontend_url: str, requests: Iterable[RequestRecord]):
        super().__init__()
        self.frontend_url = frontend_url
        self.requests = list(requests)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Requests for {}".format(self.frontend_url), id="detail-title")
        yield DataTable(
            id="request-table",
            cursor_type="row",
            zebra_stripes=True,
            show_row_labels=False,
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#request-table", DataTable)
        table.add_columns(
            "Time",
            "Method",
            "Request URI",
            "Status",
            "Upstream",
            "Backend TX",
            "Backend RX",
            "Latency",
        )
        for request in sorted(self.requests, key=lambda item: item.timestamp, reverse=True):
            table.add_row(
                request.timestamp.astimezone().strftime("%H:%M:%S"),
                request.method,
                request.uri,
                str(request.status),
                request.upstream_address,
                format_bytes(request.backend_tx_bytes),
                format_bytes(request.backend_rx_bytes),
                "{} ms".format(request.latency_ms),
            )
        table.focus()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit_monitor(self) -> None:
        self.app.exit()


class MonitorApp(App[None]):
    """Live monitor that periodically reads an Nginx access-log file."""

    TITLE = "nginx-mon"
    SUB_TITLE = "Nginx reverse proxy traffic"
    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit_monitor", "Quit"),
        Binding("ctrl+c", "quit_monitor", "Quit"),
    ]

    CSS = """
    #status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    #traffic-table {
        height: 1fr;
    }
    """

    def __init__(
        self,
        log_file: Path,
        refresh_interval: float = 1.0,
        max_records: int = 5_000,
    ):
        super().__init__()
        self.follower = LogFollower(log_file)
        self.parser = NginxJsonParser()
        self.store = TrafficStore(max_records=max_records)
        self.refresh_interval = refresh_interval
        self._parsed_request_count = 0
        self._ignored_line_count = 0

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Starting monitor...", id="status")
        yield DataTable(
            id="traffic-table",
            cursor_type="row",
            zebra_stripes=True,
            show_row_labels=False,
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#traffic-table", DataTable)
        table.add_columns(
            "Frontend URL",
            "Requests",
            "Backend TX/s",
            "Backend RX/s",
            "TX Total",
            "RX Total",
        )
        table.focus()
        self.refresh_data()
        self.set_interval(self.refresh_interval, self.refresh_data)

    def refresh_data(self) -> None:
        """Ingest newly completed requests and redraw the live summary table."""

        for line in self.follower.poll():
            record = self.parser.parse_line(line)
            if record is None:
                self._ignored_line_count += 1
                continue
            self.store.add(record)
            self._parsed_request_count += 1

        summaries = self.store.summaries(self.now())
        table = self.query_one("#traffic-table", DataTable)
        table.clear(columns=False)
        for summary in summaries:
            table.add_row(
                summary.frontend_url,
                str(summary.request_count),
                "{}/s".format(format_bytes(summary.backend_tx_rate)),
                "{}/s".format(format_bytes(summary.backend_rx_rate)),
                format_bytes(summary.backend_tx_bytes),
                format_bytes(summary.backend_rx_bytes),
                key=summary.frontend_url,
            )
        self._update_status(summaries)

    def _update_status(self, summaries: List[FrontendSummary]) -> None:
        status = self.query_one("#status", Static)
        if self.follower.last_error:
            status.update(self.follower.last_error)
            return
        status.update(
            "{} frontend(s) | {} parsed | {} ignored | {}s rolling rate"
            .format(
                len(summaries),
                self._parsed_request_count,
                self._ignored_line_count,
                self.store.rate_window_seconds,
            )
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "traffic-table":
            return
        frontend_url = str(event.row_key.value)
        requests = self.store.requests_for(frontend_url)
        if requests:
            self.push_screen(RequestDetailScreen(frontend_url, requests))

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_quit_monitor(self) -> None:
        self.exit()
