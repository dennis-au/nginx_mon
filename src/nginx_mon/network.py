"""Resolve Nginx listener addresses to NetworkManager connection names."""

import json
import subprocess
import time
from typing import Callable, Dict, Optional


class NetworkManagerResolver:
    """Cache active NetworkManager connections for the monitor UI."""

    def __init__(
        self,
        command_runner: Optional[Callable] = None,
        refresh_seconds: float = 30.0,
    ) -> None:
        self._command_runner = command_runner or subprocess.run
        self._refresh_seconds = refresh_seconds
        self._last_refresh: Optional[float] = None
        self._address_connections: Dict[str, str] = {}

    def connection_for(self, listener_address: str) -> str:
        """Return the active connection for a local listener address."""

        if not listener_address or listener_address == "-":
            return "-"
        if self._last_refresh is None or (
            time.monotonic() - self._last_refresh >= self._refresh_seconds
        ):
            self._refresh()
        return self._address_connections.get(listener_address, "-")

    def _refresh(self) -> None:
        self._last_refresh = time.monotonic()
        try:
            addresses = self._run(("ip", "-j", "address", "show"))
            payload = json.loads(addresses.stdout or "[]")
        except (OSError, ValueError, json.JSONDecodeError):
            self._address_connections = {}
            return

        connections = {}
        try:
            network_manager = self._run(
                ("nmcli", "-g", "GENERAL.DEVICE,GENERAL.CONNECTION", "device", "show")
            )
            values = network_manager.stdout.splitlines()
            connections = {
                values[index].strip(): values[index + 1].strip()
                for index in range(0, len(values) - 1, 2)
                if values[index].strip()
                and values[index + 1].strip()
                and values[index + 1].strip() != "--"
            }
        except OSError:
            pass

        address_connections = {}
        for device in payload:
            interface = device.get("ifname", "")
            connection = connections.get(interface, interface)
            if not connection:
                continue
            for address in device.get("addr_info", []):
                local_address = address.get("local", "")
                if local_address:
                    address_connections[local_address] = connection
        self._address_connections = address_connections

    def _run(self, command):
        return self._command_runner(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
