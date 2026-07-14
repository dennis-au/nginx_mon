"""A small polling log follower that tolerates Nginx rotations."""

from pathlib import Path
from typing import List, Optional, Tuple


class LogFollower:
    """Read complete lines appended to a log file without spawning `tail`."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._offset = 0
        self._file_id: Optional[Tuple[int, int]] = None
        self._partial = ""
        self.last_error: Optional[str] = None

    def poll(self) -> List[str]:
        """Return newly written complete lines, resetting after rotation."""

        try:
            stat = self.path.stat()
        except OSError as error:
            self.last_error = "Waiting for {}: {}".format(self.path, error.strerror or error)
            return []

        file_id = (stat.st_dev, stat.st_ino)
        if self._file_id != file_id or stat.st_size < self._offset:
            self._file_id = file_id
            self._offset = 0
            self._partial = ""

        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(self._offset)
                data = handle.read()
                self._offset = handle.tell()
        except OSError as error:
            self.last_error = "Cannot read {}: {}".format(self.path, error.strerror or error)
            return []

        self.last_error = None
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
