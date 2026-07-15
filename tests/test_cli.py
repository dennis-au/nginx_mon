from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nginx_mon.cli import DEFAULT_LOG_FILE, build_parser, main
from nginx_mon.discovery import NginxDiscoveryError


def test_cli_uses_documented_monitor_defaults():
    args = build_parser().parse_args([])

    assert args.log_file is None
    assert args.refresh_interval == 1.0
    assert args.max_records == 5_000


@pytest.mark.parametrize(
    "arguments",
    [
        ["--refresh-interval", "0"],
        ["--refresh-interval", "not-a-number"],
        ["--max-records", "0"],
    ],
)
def test_cli_rejects_non_positive_monitor_settings(arguments):
    with pytest.raises(SystemExit):
        build_parser().parse_args(arguments)


def test_main_constructs_and_runs_the_monitor():
    app = Mock()
    with patch("nginx_mon.cli.MonitorApp", return_value=app) as app_class:
        assert main(["--log-file", "/tmp/access.json.log", "--max-records", "10"]) == 0

    app_class.assert_called_once_with(
        log_file=Path("/tmp/access.json.log"),
        refresh_interval=1.0,
        max_records=10,
    )
    app.run.assert_called_once_with()


def test_main_uses_the_default_log_file_without_discovery():
    app = Mock()
    with patch("nginx_mon.cli.MonitorApp", return_value=app) as app_class:
        assert main([]) == 0

    app_class.assert_called_once_with(
        log_file=DEFAULT_LOG_FILE,
        refresh_interval=1.0,
        max_records=5_000,
    )


def test_main_detects_a_log_file_when_requested():
    app = Mock()
    detected_log = Path("/custom/nginx/logs/nginx-mon.json")
    with patch("nginx_mon.cli.MonitorApp", return_value=app) as app_class, patch(
        "nginx_mon.cli.discover_log_file", return_value=detected_log
    ) as discover:
        assert main(["--detect-nginx"]) == 0

    discover.assert_called_once_with(nginx_pid=None)
    app_class.assert_called_once_with(
        log_file=detected_log,
        refresh_interval=1.0,
        max_records=5_000,
    )


def test_explicit_log_file_overrides_nginx_discovery():
    app = Mock()
    explicit_log = Path("/tmp/access.json.log")
    with patch("nginx_mon.cli.MonitorApp", return_value=app) as app_class, patch(
        "nginx_mon.cli.discover_log_file"
    ) as discover:
        assert main(["--detect-nginx", "--log-file", str(explicit_log)]) == 0

    discover.assert_not_called()
    app_class.assert_called_once_with(
        log_file=explicit_log,
        refresh_interval=1.0,
        max_records=5_000,
    )


def test_nginx_pid_selects_the_matching_master_for_discovery():
    app = Mock()
    with patch("nginx_mon.cli.MonitorApp", return_value=app), patch(
        "nginx_mon.cli.discover_log_file", return_value=Path("/tmp/access.json.log")
    ) as discover:
        assert main(["--nginx-pid", "123"]) == 0

    discover.assert_called_once_with(nginx_pid=123)


def test_main_reports_discovery_failures_as_argument_errors():
    with patch(
        "nginx_mon.cli.discover_log_file",
        side_effect=NginxDiscoveryError("multiple logs"),
    ), pytest.raises(SystemExit) as error:
        main(["--detect-nginx"])

    assert error.value.code == 2
