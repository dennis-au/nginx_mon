"""Locate one active nginx-mon JSON access log through Linux procfs."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .parser import NginxJsonParser


PROC_ROOT = Path("/proc")
SAMPLE_BYTES = 64 * 1024


class NginxDiscoveryError(RuntimeError):
    """Raised when procfs cannot identify exactly one monitor log."""


@dataclass(frozen=True)
class NginxMaster:
    """The running Nginx master process and its executable path."""

    pid: int
    executable: str


def find_nginx_masters(proc_root: Path = PROC_ROOT) -> List[NginxMaster]:
    """Return Nginx master processes visible through procfs."""

    masters = []
    for process in _process_directories(proc_root):
        try:
            comm = (process / "comm").read_text(encoding="utf-8").strip()
            command = (process / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        except OSError:
            continue
        if not (comm.startswith("nginx: master") or "nginx: master process" in command):
            continue
        try:
            executable = os.readlink(process / "exe")
        except OSError:
            executable = "-"
        masters.append(NginxMaster(pid=int(process.name), executable=executable))
    return masters


def discover_log_file(
    nginx_pid: Optional[int] = None,
    proc_root: Path = PROC_ROOT,
) -> Path:
    """Return the only open file containing nginx-mon JSON records."""

    masters = find_nginx_masters(proc_root)
    if nginx_pid is not None:
        masters = [master for master in masters if master.pid == nginx_pid]
        if not masters:
            raise NginxDiscoveryError("Nginx master process {} was not found".format(nginx_pid))
    if not masters:
        raise NginxDiscoveryError("No Nginx master process was found")
    if len(masters) > 1:
        raise NginxDiscoveryError(
            "Multiple Nginx master processes found ({}); use --nginx-pid or --log-file".format(
                ", ".join(
                    "{} ({})".format(master.pid, master.executable) for master in masters
                )
            )
        )

    master = masters[0]
    candidates = _open_regular_files(proc_root, master.pid)
    parser = NginxJsonParser()
    matches = [path for path in candidates if _contains_monitor_record(path, parser)]
    if not matches:
        raise NginxDiscoveryError(
            "No nginx-mon JSON access log found for Nginx PID {}; use --log-file".format(
                master.pid
            )
        )
    if len(matches) > 1:
        raise NginxDiscoveryError(
            "Multiple nginx-mon JSON logs found ({}); use --log-file".format(
                ", ".join(str(path) for path in matches)
            )
        )
    return matches[0]


def _process_directories(proc_root: Path) -> List[Path]:
    try:
        return [path for path in proc_root.iterdir() if path.name.isdecimal()]
    except OSError:
        return []


def _open_regular_files(proc_root: Path, master_pid: int) -> List[Path]:
    process_ids = [master_pid]
    for process in _process_directories(proc_root):
        if _parent_pid(process) == master_pid:
            process_ids.append(int(process.name))

    paths = []
    seen = set()
    for pid in process_ids:
        try:
            descriptors = (proc_root / str(pid) / "fd").iterdir()
        except OSError:
            continue
        for descriptor in descriptors:
            try:
                target = os.readlink(descriptor)
                if target.endswith(" (deleted)"):
                    continue
                path = Path(target)
                if not path.is_absolute():
                    path = descriptor.parent / path
                file_stat = path.stat()
            except OSError:
                continue
            if not stat.S_ISREG(file_stat.st_mode):
                continue
            file_id: Tuple[int, int] = (file_stat.st_dev, file_stat.st_ino)
            if file_id not in seen:
                paths.append(path)
                seen.add(file_id)
    return paths


def _parent_pid(process: Path) -> Optional[int]:
    try:
        for line in (process / "status").read_text(encoding="utf-8").splitlines():
            if line.startswith("PPid:"):
                return int(line.split(":", 1)[1].strip())
    except (OSError, ValueError):
        pass
    return None


def _contains_monitor_record(path: Path, parser: NginxJsonParser) -> bool:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            offset = max(0, handle.tell() - SAMPLE_BYTES)
            handle.seek(offset)
            data = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return False

    lines = data.splitlines()
    if offset and lines:
        lines = lines[1:]
    return any(parser.parse_line(line) is not None for line in reversed(lines))
