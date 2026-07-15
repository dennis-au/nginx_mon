from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nginx_mon.cli import build_parser, main
from nginx_mon.configuration import GlobalLogResult
from nginx_mon.discovery import NginxDiscoveryError


def test_cli_uses_documented_monitor_defaults():
    args = build_parser().parse_args([])

    assert args.log_file is None
    assert args.refresh_interval == 1.0
    assert args.max_records == 5_000


def test_cli_accepts_explicit_global_json_log_management_options():
    args = build_parser().parse_args(
        ["--enable-global-json-log", "--global-log-path", "/logs/nginx-mon.json"]
    )

    assert args.enable_global_json_log is True
    assert args.disable_global_json_log is False
    assert args.global_log_path == Path("/logs/nginx-mon.json")


def test_cli_rejects_a_global_log_path_without_an_enable_operation():
    with pytest.raises(SystemExit):
        main(["--global-log-path", "/logs/nginx-mon.json"])


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


def test_main_enables_the_global_json_log_without_starting_the_monitor(capsys):
    result = GlobalLogResult(
        pid=123,
        config_file=Path("/etc/nginx/nginx.conf"),
        log_file=Path("/var/log/nginx/nginx-mon-access.json.log"),
    )
    with patch("nginx_mon.cli.enable_global_json_log", return_value=result) as enable, patch(
        "nginx_mon.cli.MonitorApp"
    ) as app_class:
        assert main(["--enable-global-json-log", "--nginx-pid", "123"]) == 0

    enable.assert_called_once_with(
        nginx_pid=123,
        log_file=Path("/var/log/nginx/nginx-mon-access.json.log"),
    )
    app_class.assert_not_called()
    assert "Enabled global JSON log" in capsys.readouterr().out


def test_main_disables_the_global_json_log_without_starting_the_monitor(capsys):
    result = GlobalLogResult(
        pid=123,
        config_file=Path("/etc/nginx/nginx.conf"),
        log_file=Path("/var/log/nginx/nginx-mon-access.json.log"),
    )
    with patch("nginx_mon.cli.disable_global_json_log", return_value=result) as disable, patch(
        "nginx_mon.cli.MonitorApp"
    ) as app_class:
        assert main(["--disable-global-json-log"]) == 0

    disable.assert_called_once_with(nginx_pid=None)
    app_class.assert_not_called()
    assert "Disabled global JSON log" in capsys.readouterr().out


def test_main_auto_detects_a_log_file_without_command_line_options():
    app = Mock()
    detected_log = Path("/custom/nginx/logs/nginx-mon.json")
    with patch("nginx_mon.cli.MonitorApp", return_value=app) as app_class, patch(
        "nginx_mon.cli.discover_log_file", return_value=detected_log
    ) as discover:
        assert main([]) == 0

    discover.assert_called_once_with(nginx_pid=None)
    app_class.assert_called_once_with(
        log_file=detected_log,
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


@pytest.mark.parametrize("arguments", [[], ["--detect-nginx"]])
def test_main_reports_auto_discovery_failures_as_argument_errors(arguments):
    with patch("nginx_mon.cli.MonitorApp"), patch(
        "nginx_mon.cli.discover_log_file", side_effect=NginxDiscoveryError("multiple logs")
    ), pytest.raises(SystemExit) as error:
        main(arguments)

    assert error.value.code == 2
