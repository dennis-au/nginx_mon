"""PyInstaller entry point for the nginx-mon executable."""

from nginx_mon.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
