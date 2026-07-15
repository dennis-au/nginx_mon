"""A small polling log follower that tolerates Nginx rotations."""

from pathlib import Path
from typing import List, Optional, TextIO, Tuple


class LogFollower:
    """Read complete lines appended to a log file without spawning `tail`."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._offset = 0
        self._file_id: Optional[Tuple[int, int]] = None
        self._handle: Optional[TextIO] = None
        self._partial = ""
        self.last_error: Optional[str] = None

    def poll(self) -> List[str]:
        """Return newly written complete lines, resetting after rotation."""

        try:
            stat = self.path.stat()
        except OSError as error:
            self.last_error = "Waiting for {}: {}".format(self.path, error.strerror or error)
            if self._handle is None:
                return []
            try:
                return self._consume(self._read_pending())
            except OSError as read_error:
                self.last_error = "Cannot read {}: {}".format(
                    self.path, read_error.strerror or read_error
                )
                return []

        self.last_error = None
        file_id = (stat.st_dev, stat.st_ino)
        try:
            if self._handle is None:
                self._open(file_id)
                return self._consume(self._read_pending())
            if self._file_id != file_id:
                lines = self._consume(self._read_pending())
                self._handle.close()
                self._handle = None
                self._open(file_id)
                return lines + self._consume(self._read_pending())
            if stat.st_size < self._offset:
                self._handle.seek(0)
                self._offset = 0
                self._partial = ""
            return self._consume(self._read_pending())
        except OSError as error:
            self.last_error = "Cannot read {}: {}".format(self.path, error.strerror or error)
            return []

    def _open(self, file_id: Tuple[int, int]) -> None:
        self._handle = self.path.open("r", encoding="utf-8", errors="replace")
        self._file_id = file_id
        self._offset = 0
        self._partial = ""

    def _read_pending(self) -> str:
        assert self._handle is not None
        self._handle.seek(self._offset)
        data = self._handle.read()
        self._offset = self._handle.tell()
        return data

    def _consume(self, data: str) -> List[str]:
        self._partial += data
        complete_lines = []
        remaining = ""
        for line in self._partial.splitlines(keepends=True):
            if line.endswith("\n") or line.endswith("\r"):
                complete_lines.append(line)
            else:
                remaining = line
        self._partial = remaining
        return complete_lines
