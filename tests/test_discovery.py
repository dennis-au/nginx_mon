import json

import pytest

from nginx_mon.discovery import NginxDiscoveryError, discover_log_file, find_nginx_masters


def _process(proc_root, pid, comm, cmdline, parent_pid=1):
    process = proc_root / str(pid)
    (process / "fd").mkdir(parents=True)
    (process / "comm").write_text(comm, encoding="utf-8")
    (process / "cmdline").write_bytes(cmdline)
    (process / "status").write_text("Name:\tnginx\nPPid:\t{}\n".format(parent_pid))
    (process / "exe").symlink_to("/custom/nginx/sbin/nginx")
    return process


def _json_log(path, host="api.example.test"):
    path.write_text(
        json.dumps(
            {
                "time": "2026-07-15T12:34:56+00:00",
                "host": host,
                "request": "GET / HTTP/1.1",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_discovers_one_json_log_from_a_worker_fd_and_deduplicates_it(tmp_path):
    proc_root = tmp_path / "proc"
    master = _process(
        proc_root,
        100,
        "nginx: master p",
        b"nginx: master process /custom/nginx/sbin/nginx\0",
    )
    worker = _process(proc_root, 101, "nginx: worker p", b"nginx: worker process\0", 100)
    log_file = tmp_path / "logs" / "nginx-mon.json"
    log_file.parent.mkdir()
    _json_log(log_file)
    (master / "fd" / "7").symlink_to(log_file)
    (worker / "fd" / "9").symlink_to(log_file)

    master_process = find_nginx_masters(proc_root=proc_root)[0]

    assert master_process.executable == "/custom/nginx/sbin/nginx"
    assert discover_log_file(proc_root=proc_root) == log_file


def test_requires_an_explicit_path_when_multiple_json_logs_are_open(tmp_path):
    proc_root = tmp_path / "proc"
    master = _process(
        proc_root,
        100,
        "nginx: master p",
        b"nginx: master process /custom/nginx/sbin/nginx\0",
    )
    first_log = tmp_path / "first.json"
    second_log = tmp_path / "second.json"
    _json_log(first_log, "one.example.test")
    _json_log(second_log, "two.example.test")
    (master / "fd" / "7").symlink_to(first_log)
    (master / "fd" / "8").symlink_to(second_log)

    with pytest.raises(NginxDiscoveryError, match="Multiple nginx-mon JSON logs"):
        discover_log_file(proc_root=proc_root)


def test_nginx_pid_selects_one_master_when_multiple_instances_are_running(tmp_path):
    proc_root = tmp_path / "proc"
    first_master = _process(
        proc_root, 100, "nginx: master p", b"nginx: master process /one/nginx\0"
    )
    _process(proc_root, 200, "nginx: master p", b"nginx: master process /two/nginx\0")
    log_file = tmp_path / "first.json"
    _json_log(log_file)
    (first_master / "fd" / "7").symlink_to(log_file)

    assert discover_log_file(nginx_pid=100, proc_root=proc_root) == log_file


def test_ignores_deleted_non_regular_and_invalid_log_candidates(tmp_path):
    proc_root = tmp_path / "proc"
    master = _process(
        proc_root,
        100,
        "nginx: master p",
        b"nginx: master process /custom/nginx/sbin/nginx\0",
    )
    deleted_log = tmp_path / "old.json (deleted)"
    invalid_log = tmp_path / "access.log"
    deleted_log.write_text("ignored\n", encoding="utf-8")
    invalid_log.write_text("not json\n", encoding="utf-8")
    (master / "fd" / "7").symlink_to(deleted_log)
    (master / "fd" / "8").symlink_to("/dev/null")
    (master / "fd" / "9").symlink_to(invalid_log)
    (master / "fd" / "10").symlink_to(tmp_path / "gone.json")

    with pytest.raises(NginxDiscoveryError, match="No nginx-mon JSON access log"):
        discover_log_file(proc_root=proc_root)


def test_rejects_an_empty_json_log(tmp_path):
    proc_root = tmp_path / "proc"
    master = _process(
        proc_root,
        100,
        "nginx: master p",
        b"nginx: master process /custom/nginx/sbin/nginx\0",
    )
    log_file = tmp_path / "empty.json"
    log_file.touch()
    (master / "fd" / "7").symlink_to(log_file)

    with pytest.raises(NginxDiscoveryError, match="No nginx-mon JSON access log"):
        discover_log_file(proc_root=proc_root)


def test_requires_a_master_when_multiple_nginx_instances_are_running(tmp_path):
    proc_root = tmp_path / "proc"
    first_master = _process(
        proc_root, 100, "nginx: master p", b"nginx: master process /one/nginx\0"
    )
    second_master = _process(
        proc_root, 200, "nginx: master p", b"nginx: master process /two/nginx\0"
    )
    first_master.joinpath("exe").unlink()
    first_master.joinpath("exe").symlink_to("/one/nginx")
    second_master.joinpath("exe").unlink()
    second_master.joinpath("exe").symlink_to("/two/nginx")

    with pytest.raises(NginxDiscoveryError, match="Multiple Nginx master processes") as error:
        discover_log_file(proc_root=proc_root)

    assert "100 (/one/nginx)" in str(error.value)
    assert "200 (/two/nginx)" in str(error.value)
