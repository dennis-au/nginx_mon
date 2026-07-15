import signal
import subprocess

import pytest

from nginx_mon.configuration import (
    NginxConfigurationError,
    _select_running_master,
    disable_global_json_log,
    enable_global_json_log,
)


def _nginx_version_result(command, config_file):
    return subprocess.CompletedProcess(
        command,
        0,
        stdout="",
        stderr="nginx version: nginx/1.20.1\nconfigure arguments: --conf-path={}\n".format(
            config_file
        ),
    )


def _runner_for(config_file, commands, fail_test=False):
    def run(command, **_kwargs):
        commands.append(command)
        if command[1] == "-V":
            return _nginx_version_result(command, config_file)
        if fail_test:
            return subprocess.CompletedProcess(
                command, 1, stdout="", stderr="nginx: [emerg] invalid configuration"
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="syntax is ok")

    return run


def test_refuses_to_manage_a_master_owned_by_another_user(tmp_path, monkeypatch):
    proc_root = tmp_path / "proc"
    process = proc_root / "321"
    process.mkdir(parents=True)
    (process / "comm").write_text("nginx: master p\n", encoding="utf-8")
    (process / "cmdline").write_bytes(b"nginx: master process /custom/sbin/nginx\0")
    (process / "status").write_text("Uid:\t1000\t1000\t1000\t1000\n", encoding="utf-8")
    (process / "exe").symlink_to("/custom/sbin/nginx")
    monkeypatch.setattr("nginx_mon.configuration.os.geteuid", lambda: 0)

    with pytest.raises(NginxConfigurationError, match="owned by UID 1000"):
        _select_running_master(None, proc_root)


def test_enable_adds_a_global_json_mirror_without_replacing_the_existing_default(
    tmp_path, monkeypatch
):
    config_file = tmp_path / "nginx.conf"
    config_file.write_text(
        "events {}\nhttp {\n    access_log /var/log/nginx/access.log main;\n}\n",
        encoding="utf-8",
    )
    commands = []
    signals = []
    monkeypatch.setattr(
        "nginx_mon.configuration._select_running_master",
        lambda nginx_pid, proc_root: (321, "/custom/sbin/nginx"),
    )

    result = enable_global_json_log(
        log_file=tmp_path / "monitor.json",
        runner=_runner_for(config_file, commands),
        signal_sender=lambda pid, sig: signals.append((pid, sig)),
    )

    managed_file = tmp_path / "nginx-mon-global.conf"
    assert result.log_file == tmp_path / "monitor.json"
    assert config_file.read_text(encoding="utf-8") == (
        "events {{}}\nhttp {{\n"
        "    access_log /var/log/nginx/access.log main;\n"
        "    # nginx-mon managed global JSON access log\n"
        "    include {0};\n"
        "}}\n".format(managed_file)
    )
    assert "access_log {} nginx_mon_global_json;".format(result.log_file) in managed_file.read_text(
        encoding="utf-8"
    )
    assert commands[0] == ["/custom/sbin/nginx", "-V"]
    assert commands[1] == ["/custom/sbin/nginx", "-t", "-c", str(config_file)]
    assert signals == [(321, signal.SIGHUP)]


def test_enable_rejects_a_log_file_in_a_missing_directory_before_editing_config(
    tmp_path, monkeypatch
):
    config_file = tmp_path / "nginx.conf"
    original = "http {}\n"
    config_file.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        "nginx_mon.configuration._select_running_master",
        lambda nginx_pid, proc_root: (321, "/custom/sbin/nginx"),
    )

    with pytest.raises(NginxConfigurationError, match="directory does not exist"):
        enable_global_json_log(
            log_file=tmp_path / "missing" / "monitor.json",
            runner=lambda *_args, **_kwargs: pytest.fail("nginx must not run"),
            signal_sender=lambda _pid, _signal: pytest.fail("nginx must not reload"),
        )

    assert config_file.read_text(encoding="utf-8") == original


def test_disable_removes_only_the_managed_global_mirror(tmp_path, monkeypatch):
    config_file = tmp_path / "nginx.conf"
    config_file.write_text(
        "http {\n    access_log /var/log/nginx/access.log main;\n}\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        "nginx_mon.configuration._select_running_master",
        lambda nginx_pid, proc_root: (321, "/custom/sbin/nginx"),
    )
    commands = []
    runner = _runner_for(config_file, commands)

    enable_global_json_log(
        log_file=tmp_path / "monitor.json",
        runner=runner,
        signal_sender=lambda _pid, _signal: None,
    )
    result = disable_global_json_log(
        runner=runner,
        signal_sender=lambda _pid, _signal: None,
    )

    assert result.log_file == tmp_path / "monitor.json"
    assert config_file.read_text(encoding="utf-8") == (
        "http {\n    access_log /var/log/nginx/access.log main;\n}\n"
    )
    assert not (tmp_path / "nginx-mon-global.conf").exists()


def test_enable_restores_the_original_configuration_when_nginx_validation_fails(
    tmp_path, monkeypatch
):
    config_file = tmp_path / "nginx.conf"
    original = "http {\n    access_log /var/log/nginx/access.log main;\n}\n"
    config_file.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        "nginx_mon.configuration._select_running_master",
        lambda nginx_pid, proc_root: (321, "/custom/sbin/nginx"),
    )

    with pytest.raises(NginxConfigurationError, match=r"nginx: \[emerg\]"):
        enable_global_json_log(
            log_file=tmp_path / "monitor.json",
            runner=_runner_for(config_file, [], fail_test=True),
            signal_sender=lambda _pid, _signal: pytest.fail("nginx must not reload"),
        )

    assert config_file.read_text(encoding="utf-8") == original
    assert not (tmp_path / "nginx-mon-global.conf").exists()
