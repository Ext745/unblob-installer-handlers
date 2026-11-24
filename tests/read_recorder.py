"""A File stand-in that records how far chunk calculation reads (NFR-SEC-03).

Wraps unblob's File. Every read() and every slice is passed through, and two
things are kept:

- highest: one past the last byte any read or slice asked for, so a test can
  assert that a handler never asks for bytes at or past the end of its input
  (a declared length trusted beyond the data);
- longest: the most bytes one read or slice asked for, so a test can assert
  that a handler reads a bounded window, not the whole input.

find() is passed through unrecorded: its end argument is a search bound, not a
read. Handlers that only use seek/read/tell or slicing are fully covered.
A handler that passes the file to struct.unpack_from (the PE helpers) cannot
take a ReadRecorder: a Python class gets the buffer protocol only from Python
3.12 on, and the package supports 3.10. Test those with a plain File.
"""

from types import TracebackType
from typing import cast

from unblob.file_utils import File


class ReadRecorder:
    def __init__(self, data: bytes) -> None:
        self._file = File.from_bytes(data)
        self._size = len(data)
        self.highest = 0
        self.longest = 0

    def __enter__(self) -> "ReadRecorder":
        return self

    def as_file(self) -> File:
        """Return this recorder typed as the File that calculate_chunk takes."""
        return cast("File", self)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._file.close()

    def _asked(self, start: int, stop: int) -> None:
        self.highest = max(self.highest, stop)
        self.longest = max(self.longest, stop - start)

    def read(self, n: int | None = -1) -> bytes:
        pos = self._file.tell()
        self._asked(pos, self._size if n is None or n < 0 else pos + n)
        return self._file.read(n)

    def __len__(self) -> int:
        return self._size

    def size(self) -> int:
        return self._size

    def __getitem__(self, key: slice) -> bytes:
        start = key.start or 0
        self._asked(start, self._size if key.stop is None else key.stop)
        return self._file[key]

    def __getattr__(self, name: str):
        # seek, tell, find, ... go to the real File unchanged.
        return getattr(self._file, name)

    @property
    def read_past_end(self) -> bool:
        return self.highest > self._size
