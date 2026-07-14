from types import SimpleNamespace
from unittest.mock import patch

from nginx_mon.network import NetworkManagerResolver


def test_resolver_maps_listener_address_to_networkmanager_connection():
    def run_command(command, **_kwargs):
        if command[0] == "ip":
            return SimpleNamespace(
                stdout=(
                    '[{"ifname":"lo","addr_info":[{"local":"127.0.0.1"}]},'
                    '{"ifname":"ens18","addr_info":[{"local":"192.168.0.101"}]}]'
                )
            )
        return SimpleNamespace(stdout="lo\nlo\nens18\nens18\n")

    resolver = NetworkManagerResolver(command_runner=run_command)

    assert resolver.connection_for("192.168.0.101") == "ens18"
    assert resolver.connection_for("127.0.0.1") == "lo"
    assert resolver.connection_for("192.0.2.1") == "-"


def test_resolver_handles_unavailable_host_tools():
    def run_command(_command, **_kwargs):
        raise OSError("command unavailable")

    assert NetworkManagerResolver(command_runner=run_command).connection_for("192.168.0.101") == "-"


def test_resolver_refreshes_immediately_after_host_startup():
    def run_command(command, **_kwargs):
        if command[0] == "ip":
            return SimpleNamespace(
                stdout='[{"ifname":"ens18","addr_info":[{"local":"192.168.0.101"}]}]'
            )
        return SimpleNamespace(stdout="ens18\nens18\n")

    with patch("nginx_mon.network.time.monotonic", return_value=5.0):
        resolver = NetworkManagerResolver(command_runner=run_command)
        assert resolver.connection_for("192.168.0.101") == "ens18"
