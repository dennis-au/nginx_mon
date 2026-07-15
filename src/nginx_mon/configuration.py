"""Manage nginx-mon's optional global JSON access-log mirror."""

import os
import re
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

from .discovery import NginxMaster, PROC_ROOT, find_nginx_masters


DEFAULT_GLOBAL_LOG_FILE = Path("/var/log/nginx/nginx-mon-access.json.log")
MANAGED_FRAGMENT_NAME = "nginx-mon-global.conf"
MANAGED_INCLUDE_COMMENT = "# nginx-mon managed global JSON access log"
MANAGED_FRAGMENT_COMMENT = "# This file is managed by nginx-mon."
LOG_FORMAT_NAME = "nginx_mon_global_json"


class NginxConfigurationError(RuntimeError):
    """Raised when nginx-mon cannot safely manage the global access log."""


@dataclass(frozen=True)
class GlobalLogResult:
    """The Nginx instance and log path managed by a completed operation."""

    pid: int
    config_file: Path
    log_file: Path


Runner = Callable[..., subprocess.CompletedProcess]
SignalSender = Callable[[int, signal.Signals], None]


def enable_global_json_log(
    nginx_pid: Optional[int] = None,
    log_file: Path = DEFAULT_GLOBAL_LOG_FILE,
    proc_root: Path = PROC_ROOT,
    runner: Runner = subprocess.run,
    signal_sender: SignalSender = os.kill,
) -> GlobalLogResult:
    """Add a managed JSON access log at Nginx's global ``http`` level.

    The existing default access log remains in place. Nginx writes the managed
    JSON log as an additional global default for servers that inherit it.
    """

    log_file = Path(log_file).expanduser().resolve()
    if not log_file.parent.is_dir():
        raise NginxConfigurationError(
            "JSON log directory does not exist: {}".format(log_file.parent)
        )
    pid, executable = _select_running_master(nginx_pid, proc_root)
    config_file = _configuration_path(executable, runner)
    fragment_file = config_file.with_name(MANAGED_FRAGMENT_NAME)
    original_config = _read_text(config_file)
    original_fragment = _read_optional_text(fragment_file)
    include = _managed_include(fragment_file)
    managed_block = "{}\n{}".format(MANAGED_INCLUDE_COMMENT, include)

    if "{}\n".format(_indented(managed_block)) in original_config:
        if original_fragment is None or not original_fragment.startswith(MANAGED_FRAGMENT_COMMENT):
            raise NginxConfigurationError(
                "Managed include {} exists but its fragment is missing or was changed; "
                "remove it manually before retrying".format(fragment_file)
            )
        updated_config = original_config
    else:
        updated_config = _insert_managed_include(original_config, include)

    updated_fragment = _managed_fragment(log_file)
    if updated_config == original_config and updated_fragment == original_fragment:
        return GlobalLogResult(pid=pid, config_file=config_file, log_file=log_file)

    try:
        if updated_config != original_config:
            _replace_text(config_file, updated_config)
        if updated_fragment != original_fragment:
            _replace_text(fragment_file, updated_fragment)
        _validate_and_reload(executable, config_file, pid, runner, signal_sender)
    except (OSError, NginxConfigurationError):
        _restore_text(config_file, original_config)
        _restore_optional_text(fragment_file, original_fragment)
        raise

    return GlobalLogResult(pid=pid, config_file=config_file, log_file=log_file)


def disable_global_json_log(
    nginx_pid: Optional[int] = None,
    proc_root: Path = PROC_ROOT,
    runner: Runner = subprocess.run,
    signal_sender: SignalSender = os.kill,
) -> GlobalLogResult:
    """Remove nginx-mon's managed global JSON access-log mirror."""

    pid, executable = _select_running_master(nginx_pid, proc_root)
    config_file = _configuration_path(executable, runner)
    fragment_file = config_file.with_name(MANAGED_FRAGMENT_NAME)
    original_config = _read_text(config_file)
    original_fragment = _read_optional_text(fragment_file)
    include = _managed_include(fragment_file)
    managed_block = "{}\n{}".format(MANAGED_INCLUDE_COMMENT, include)

    if "{}\n".format(_indented(managed_block)) not in original_config:
        raise NginxConfigurationError(
            "No nginx-mon managed global JSON log is enabled in {}".format(config_file)
        )
    if original_fragment is None or not original_fragment.startswith(MANAGED_FRAGMENT_COMMENT):
        raise NginxConfigurationError(
            "Managed fragment {} is missing or was changed; remove the include manually".format(
                fragment_file
            )
        )

    log_file = _log_path_from_fragment(original_fragment)
    updated_config = _remove_managed_include(original_config, managed_block)
    try:
        _replace_text(config_file, updated_config)
        _validate_and_reload(executable, config_file, pid, runner, signal_sender)
    except (OSError, NginxConfigurationError):
        _restore_text(config_file, original_config)
        raise

    try:
        fragment_file.unlink()
    except OSError as error:
        raise NginxConfigurationError(
            "Nginx reloaded but could not remove managed fragment {}: {}".format(fragment_file, error)
        ) from error
    return GlobalLogResult(pid=pid, config_file=config_file, log_file=log_file)


def _select_running_master(nginx_pid: Optional[int], proc_root: Path) -> Tuple[int, str]:
    masters = find_nginx_masters(proc_root)
    if nginx_pid is not None:
        masters = [master for master in masters if master.pid == nginx_pid]
    if not masters:
        if nginx_pid is not None:
            raise NginxConfigurationError("Nginx master process {} was not found".format(nginx_pid))
        raise NginxConfigurationError("No Nginx master process was found")
    if len(masters) > 1:
        raise NginxConfigurationError(
            "Multiple Nginx master processes found ({}); use --nginx-pid".format(
                ", ".join("{} ({})".format(master.pid, master.executable) for master in masters)
            )
        )
    master: NginxMaster = masters[0]
    owner_uid = _master_effective_uid(proc_root, master.pid)
    current_uid = os.geteuid()
    if owner_uid != current_uid:
        raise NginxConfigurationError(
            "Refusing to manage Nginx PID {} owned by UID {}; run nginx-mon as that user".format(
                master.pid, owner_uid
            )
        )
    if master.executable == "-":
        raise NginxConfigurationError(
            "Cannot read /proc/{}/exe for the Nginx master process".format(master.pid)
        )
    return master.pid, master.executable


def _master_effective_uid(proc_root: Path, pid: int) -> int:
    try:
        status = (proc_root / str(pid) / "status").read_text(encoding="utf-8")
    except OSError as error:
        raise NginxConfigurationError(
            "Cannot read ownership for Nginx master process {}: {}".format(pid, error)
        ) from error
    for line in status.splitlines():
        if line.startswith("Uid:"):
            fields = line.split()
            try:
                return int(fields[2])
            except (IndexError, ValueError) as error:
                raise NginxConfigurationError(
                    "Cannot parse ownership for Nginx master process {}".format(pid)
                ) from error
    raise NginxConfigurationError("Cannot read ownership for Nginx master process {}".format(pid))


def _configuration_path(executable: str, runner: Runner) -> Path:
    try:
        result = runner([executable, "-V"], capture_output=True, text=True, check=False)
    except OSError as error:
        raise NginxConfigurationError(
            "Cannot run Nginx executable {}: {}".format(executable, error)
        ) from error
    output = "{}\n{}".format(result.stdout or "", result.stderr or "")
    if result.returncode != 0:
        raise NginxConfigurationError(
            "{} -V failed: {}".format(executable, _command_output(output))
        )
    conf_path = _configure_argument(output, "conf-path")
    if conf_path is None:
        raise NginxConfigurationError(
            "Nginx executable {} did not report --conf-path in nginx -V output".format(executable)
        )
    config_file = Path(conf_path)
    if not config_file.is_absolute():
        prefix = _configure_argument(output, "prefix")
        if prefix is None:
            raise NginxConfigurationError(
                "Nginx reported relative --conf-path {} without --prefix".format(conf_path)
            )
        config_file = Path(prefix) / config_file
    return config_file.expanduser().resolve()


def _configure_argument(output: str, name: str) -> Optional[str]:
    match = re.search(r"--{}=(?:'([^']*)'|\"([^\"]*)\"|(\S+))".format(re.escape(name)), output)
    if match is None:
        return None
    return next(value for value in match.groups() if value is not None)


def _managed_include(fragment_file: Path) -> str:
    return "include {};".format(fragment_file)


def _managed_fragment(log_file: Path) -> str:
    return """{comment}
log_format {format_name} escape=json '{{'
    '\"time\":\"$time_iso8601\",'
    '\"scheme\":\"$scheme\",'
    '\"host\":\"$host\",'
    '\"server_port\":\"$server_port\",'
    '\"server_addr\":\"$server_addr\",'
    '\"source_addr\":\"$remote_addr\",'
    '\"source_port\":\"$remote_port\",'
    '\"ssl_protocol\":\"$ssl_protocol\",'
    '\"request\":\"$request\",'
    '\"method\":\"$request_method\",'
    '\"uri\":\"$request_uri\",'
    '\"status\":\"$status\",'
    '\"upstream_addr\":\"$upstream_addr\",'
    '\"request_length\":\"$request_length\",'
    '\"bytes_sent\":\"$bytes_sent\",'
    '\"upstream_bytes_sent\":\"$upstream_bytes_sent\",'
    '\"upstream_bytes_received\":\"$upstream_bytes_received\",'
    '\"request_time\":\"$request_time\",'
    '\"upstream_response_time\":\"$upstream_response_time\"'
    '}}';
access_log {log_file} {format_name};
""".format(comment=MANAGED_FRAGMENT_COMMENT, format_name=LOG_FORMAT_NAME, log_file=log_file)


def _log_path_from_fragment(fragment: str) -> Path:
    match = re.search(
        r"^access_log\s+(\S+)\s+{};$".format(re.escape(LOG_FORMAT_NAME)), fragment, re.MULTILINE
    )
    if match is None:
        raise NginxConfigurationError("Managed fragment has an invalid access_log directive")
    return Path(match.group(1))


def _insert_managed_include(config: str, include: str) -> str:
    block_end = _http_block_end(config)
    insertion = "    {}\n    {}\n".format(MANAGED_INCLUDE_COMMENT, include)
    return "{}{}{}".format(config[:block_end], insertion, config[block_end:])


def _remove_managed_include(config: str, managed_block: str) -> str:
    block = "{}\n".format(_indented(managed_block))
    if block not in config:
        raise NginxConfigurationError("Managed include is not in its expected form")
    return config.replace(block, "", 1)


def _indented(value: str) -> str:
    return "    {}".format(value.replace("\n", "\n    "))


def _http_block_end(config: str) -> int:
    tokens = _nginx_tokens(config)
    depth = 0
    for index, (value, _start, _end) in enumerate(tokens):
        if value == "{":
            depth += 1
            continue
        if value == "}":
            depth -= 1
            continue
        if value == "http" and depth == 0 and index + 1 < len(tokens) and tokens[index + 1][0] == "{":
            inner_depth = 1
            for candidate, _candidate_start, candidate_end in tokens[index + 2 :]:
                if candidate == "{":
                    inner_depth += 1
                elif candidate == "}":
                    inner_depth -= 1
                    if inner_depth == 0:
                        return candidate_end - 1
    raise NginxConfigurationError("Could not find a top-level http block in the Nginx configuration")


def _nginx_tokens(config: str) -> Sequence[Tuple[str, int, int]]:
    tokens = []
    index = 0
    while index < len(config):
        character = config[index]
        if character.isspace():
            index += 1
            continue
        if character == "#":
            newline = config.find("\n", index)
            index = len(config) if newline == -1 else newline + 1
            continue
        if character in "{};":
            tokens.append((character, index, index + 1))
            index += 1
            continue
        if character in "'\"":
            quote = character
            start = index
            index += 1
            while index < len(config):
                if config[index] == "\\":
                    index += 2
                elif config[index] == quote:
                    index += 1
                    break
                else:
                    index += 1
            tokens.append((config[start:index], start, index))
            continue
        start = index
        while index < len(config) and not config[index].isspace() and config[index] not in "#{};'\"":
            index += 1
        tokens.append((config[start:index], start, index))
    return tokens


def _validate_and_reload(
    executable: str,
    config_file: Path,
    pid: int,
    runner: Runner,
    signal_sender: SignalSender,
) -> None:
    try:
        result = runner(
            [executable, "-t", "-c", str(config_file)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise NginxConfigurationError("Cannot validate Nginx configuration: {}".format(error)) from error
    output = "{}\n{}".format(result.stdout or "", result.stderr or "")
    if result.returncode != 0:
        raise NginxConfigurationError(
            "Nginx configuration validation failed: {}".format(_command_output(output))
        )
    try:
        signal_sender(pid, signal.SIGHUP)
    except OSError as error:
        raise NginxConfigurationError(
            "Nginx configuration validated but reload signal to PID {} failed: {}".format(pid, error)
        ) from error


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise NginxConfigurationError("Cannot read Nginx configuration {}: {}".format(path, error)) from error


def _read_optional_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise NginxConfigurationError("Cannot read managed fragment {}: {}".format(path, error)) from error


def _replace_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original_stat = None
    try:
        original_stat = path.stat()
    except FileNotFoundError:
        pass
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as temporary:
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        if original_stat is not None:
            os.chmod(temporary_path, original_stat.st_mode)
            try:
                os.chown(temporary_path, original_stat.st_uid, original_stat.st_gid)
            except PermissionError:
                pass
            shutil.copystat(path, temporary_path, follow_symlinks=False)
        else:
            os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _restore_text(path: Path, content: str) -> None:
    try:
        _replace_text(path, content)
    except OSError:
        pass


def _restore_optional_text(path: Path, content: Optional[str]) -> None:
    if content is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        return
    _restore_text(path, content)


def _command_output(output: str) -> str:
    return output.strip() or "no output"
