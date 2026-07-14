"""Command-line entry point for nginx-mon."""

import argparse
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .app import MonitorApp

DEFAULT_LOG_FILE = Path("/var/log/nginx/nginx-mon-access.json.log")
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
        default=DEFAULT_LOG_FILE,
        metavar="PATH",
        help="Nginx JSON access log to follow (default: %(default)s)",
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
    args = build_parser().parse_args(argv)
    app = MonitorApp(
        log_file=args.log_file,
        refresh_interval=args.refresh_interval,
        max_records=args.max_records,
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
