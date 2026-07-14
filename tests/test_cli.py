from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from nginx_mon.cli import build_parser, main


def test_cli_uses_documented_defaults():
    args = build_parser().parse_args([])

    assert args.log_file == Path("/var/log/nginx/nginx-mon-access.json.log")
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
