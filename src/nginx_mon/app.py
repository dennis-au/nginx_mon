"""Textual screens for the live Nginx traffic monitor."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, Switch

from .configuration import (
    NginxConfigurationError,
    global_json_log_is_enabled,
    toggle_global_json_log,
)
from .models import FrontendSummary, RequestRecord
from .network import NetworkManagerResolver
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


def format_endpoints(endpoints: Iterable[str], empty: str = "-") -> str:
    """Keep a multi-endpoint summary readable in a live table row."""

    values = list(endpoints)
    if not values:
        return empty
    if len(values) <= 2:
        return ", ".join(values)
    return "{}, {} (+{})".format(values[0], values[1], len(values) - 2)


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
            "Source",
            "Listen",
            "Network",
            "TLS",
            "Method",
            "Request URI",
            "Status",
            "Backend",
            "Upstream Chain",
            "Backend TX",
            "Backend RX",
            "Latency",
        )
        for request in sorted(self.requests, key=lambda item: item.timestamp, reverse=True):
            table.add_row(
                request.timestamp.astimezone().strftime("%H:%M:%S"),
                request.source_endpoint,
                request.listener_endpoint,
                request.network_connection,
                request.ssl_protocol or "Plain",
                request.method,
                request.uri,
                str(request.status),
                request.backend_endpoint,
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
    theme = "monokai"
    BINDINGS = [
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit_monitor", "Quit"),
        Binding("ctrl+c", "quit_monitor", "Quit"),
    ]

    CSS = """
    #monitor-toolbar {
        height: 3;
        padding: 0 1;
        align: left middle;
    }

    #status {
        width: 1fr;
        color: $text-muted;
    }

    #global-json-log-label {
        width: auto;
        margin-right: 1;
    }

    #global-json-log-toggle {
        width: auto;
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
        self.network_resolver = NetworkManagerResolver()
        self.store = TrafficStore(max_records=max_records)
        self.refresh_interval = refresh_interval
        self.is_paused = False
        self._parsed_request_count = 0
        self._ignored_line_count = 0

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="monitor-toolbar"):
            yield Static("Starting monitor...", id="status")
            yield Static("Global JSON Log", id="global-json-log-label")
            yield Switch(id="global-json-log-toggle", tooltip="Toggle managed global JSON logging")
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
            "Network",
            "TLS",
            "Sources",
            "Backends",
            "Requests",
            "Backend TX/s",
            "Backend RX/s",
            "TX Total",
            "RX Total",
        )
        table.focus()
        self._sync_global_json_log_toggle()
        self.refresh_data()
        self.set_interval(self.refresh_interval, self.refresh_data)

    def refresh_data(self) -> None:
        """Ingest newly completed requests and redraw the live summary table."""

        try:
            table = self.query_one("#traffic-table", DataTable)
        except NoMatches:
            # The detail screen replaces the main table until the user returns.
            return

        if self.is_paused:
            self._update_status([])
            return

        for line in self.follower.poll():
            record = self.parser.parse_line(line)
            if record is None:
                self._ignored_line_count += 1
                continue
            record = replace(
                record,
                network_connection=self.network_resolver.connection_for(record.listener_ip),
            )
            self.store.add(record)
            self._parsed_request_count += 1

        summaries = self.store.summaries(self.now())
        table.clear(columns=False)
        for summary in summaries:
            table.add_row(
                summary.frontend_url,
                format_endpoints(summary.network_connections),
                format_endpoints(summary.tls_protocols, empty="Plain"),
                format_endpoints(summary.source_endpoints),
                format_endpoints(summary.backend_endpoints),
                str(summary.request_count),
                "{}/s".format(format_bytes(summary.backend_tx_rate)),
                "{}/s".format(format_bytes(summary.backend_rx_rate)),
                format_bytes(summary.backend_tx_bytes),
                format_bytes(summary.backend_rx_bytes),
                key=summary.frontend_url,
            )
        self._update_status(summaries)

    def get_system_commands(self, screen):
        """Remove Textual's screenshot command from this operational monitor."""

        yield from (
            command
            for command in super().get_system_commands(screen)
            if command.title != "Save screenshot"
        )

    def _update_status(self, summaries: List[FrontendSummary]) -> None:
        status = self.query_one("#status", Static)
        if self.follower.last_error:
            status.update(self.follower.last_error)
            return
        if self.is_paused:
            status.update("Paused | live updates frozen")
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

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id != "global-json-log-toggle":
            return

        previous_value = not event.value
        event.switch.disabled = True
        try:
            enabled, _result = toggle_global_json_log()
            event.switch.set_reactive(Switch.value, enabled)
            event.switch.tooltip = "Toggle managed global JSON logging"
        except NginxConfigurationError as error:
            event.switch.set_reactive(Switch.value, previous_value)
            event.switch.tooltip = str(error)
        finally:
            event.switch.disabled = False

    def _sync_global_json_log_toggle(self) -> None:
        control = self.query_one("#global-json-log-toggle", Switch)
        try:
            control.set_reactive(Switch.value, global_json_log_is_enabled())
            control.disabled = False
            control.tooltip = "Toggle managed global JSON logging"
        except NginxConfigurationError as error:
            control.set_reactive(Switch.value, False)
            control.disabled = True
            control.tooltip = str(error)

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_toggle_pause(self) -> None:
        self.is_paused = not self.is_paused
        self.refresh_data()

    def action_quit_monitor(self) -> None:
        self.exit()
