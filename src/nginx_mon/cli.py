"""Command-line entry point for nginx-mon."""

import argparse
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .app import MonitorApp
from .configuration import (
    DEFAULT_GLOBAL_LOG_FILE,
    NginxConfigurationError,
    disable_global_json_log,
    enable_global_json_log,
    toggle_global_json_log,
)
from .discovery import NginxDiscoveryError, discover_log_file

DEFAULT_REFRESH_INTERVAL = 1.0
DEFAULT_MAX_RECORDS = 5_000


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor Nginx reverse-proxy traffic from a JSON access log."
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="explicit nginx-mon JSON access log to follow",
    )
    parser.add_argument(
        "--detect-nginx",
        action="store_true",
        help="explicitly request autodetection (the default behavior)",
    )
    parser.add_argument(
        "--nginx-pid",
        type=_positive_int,
        metavar="PID",
        help="select this Nginx master process for discovery or global-log management",
    )
    management = parser.add_mutually_exclusive_group()
    management.add_argument(
        "--enable-global-json-log",
        action="store_true",
        help="add nginx-mon's JSON log as an additional global Nginx access log and reload",
    )
    management.add_argument(
        "--disable-global-json-log",
        action="store_true",
        help="remove nginx-mon's managed global JSON access log and reload",
    )
    management.add_argument(
        "--toggle-global-json-log",
        action="store_true",
        help="enable or disable nginx-mon's managed global JSON access log and reload",
    )
    parser.add_argument(
        "--global-log-path",
        type=Path,
        metavar="PATH",
        help="path when --enable-global-json-log or --toggle-global-json-log enables logging (default: {})".format(
            DEFAULT_GLOBAL_LOG_FILE
        ),
    )
    parser.add_argument(
        "--refresh-interval",
        type=_positive_float,
        default=DEFAULT_REFRESH_INTERVAL,
        metavar="SECONDS",
        help="table refresh interval in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--max-records",
        type=_positive_int,
        default=DEFAULT_MAX_RECORDS,
        metavar="COUNT",
        help="maximum in-memory requests retained (default: %(default)s)",
    )
    parser.add_argument("--version", action="version", version="nginx-mon {}".format(__version__))
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.global_log_path is not None and not (
        args.enable_global_json_log or args.toggle_global_json_log
    ):
        parser.error("--global-log-path requires --enable-global-json-log or --toggle-global-json-log")
    if args.enable_global_json_log:
        try:
            result = enable_global_json_log(
                nginx_pid=args.nginx_pid,
                log_file=args.global_log_path or DEFAULT_GLOBAL_LOG_FILE,
            )
        except NginxConfigurationError as error:
            parser.error(str(error))
        print(
            "Enabled global JSON log: {} (Nginx PID {}, {})\n"
            "Start monitoring with: nginx-mon --log-file {}".format(
                result.log_file, result.pid, result.config_file, result.log_file
            )
        )
        return 0
    if args.toggle_global_json_log:
        try:
            enabled, result = toggle_global_json_log(
                nginx_pid=args.nginx_pid,
                log_file=args.global_log_path or DEFAULT_GLOBAL_LOG_FILE,
            )
        except NginxConfigurationError as error:
            parser.error(str(error))
        if enabled:
            print(
                "Enabled global JSON log: {} (Nginx PID {}, {})\n"
                "Start monitoring with: nginx-mon --log-file {}".format(
                    result.log_file, result.pid, result.config_file, result.log_file
                )
            )
        else:
            print(
                "Disabled global JSON log: {} (Nginx PID {}, {})".format(
                    result.log_file, result.pid, result.config_file
                )
            )
        return 0
    if args.disable_global_json_log:
        try:
            result = disable_global_json_log(nginx_pid=args.nginx_pid)
        except NginxConfigurationError as error:
            parser.error(str(error))
        print(
            "Disabled global JSON log: {} (Nginx PID {}, {})".format(
                result.log_file, result.pid, result.config_file
            )
        )
        return 0
    if args.log_file is not None:
        log_file = args.log_file
    else:
        try:
            log_file = discover_log_file(nginx_pid=args.nginx_pid)
        except NginxDiscoveryError as error:
            parser.error(str(error))
    app = MonitorApp(
        log_file=log_file,
        refresh_interval=args.refresh_interval,
        max_records=args.max_records,
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
