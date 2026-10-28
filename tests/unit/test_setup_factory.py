"""Setup Factory pure core (FSD §8): PKWARE scripts of Setup Factory 8 and 9, dependency modules."""

import struct

import pytest
from unblob.file_utils import InvalidInputFormat

from unblob_installers import _blast, setup_factory


def test_tc_sf_05_pkware_decodes_blast_c_vector():
    # The example in zlib contrib/blast/blast.c.
    assert _blast.decompress(bytes.fromhex("00048224258f807f"), 100) == b"AIAIAIAIAIAIA"


def _script(modules: int, files: int, size: int = 1234) -> bytes:
    # A CSetupDependency list of `modules`, its first module holding a
    # CDependencyFile list of `files`: count, class header, 4 bytes, source
    # path (length-prefixed), the first size, the stored size.
    path = b"vb6\\msvbvm60.dll"
    dep_file = (
        struct.pack("<H", files)
        + setup_factory.DEPENDENCY_FILE_CLASS
        + bytes(4)
        + bytes([len(path)])
        + path
        + struct.pack("<qq", size, size)
    )
    return (
        b"script"
        + struct.pack("<H", modules)
        + setup_factory.DEPENDENCY_CLASS
        + bytes(8)
        + dep_file
    )


@pytest.mark.parametrize(
    "modules,files,message",
    [
        (2, 1, "several Setup Factory dependency modules"),
        (1, 2, "dependency module with several files"),
    ],
)
def test_tc_sf_12_several_modules_or_files_are_declined(modules, files, message):
    # Control: the one shape the handler accepts, so the decline is caused by
    # the count and not by a malformed script.
    assert setup_factory.dependency_size(_script(1, 1)) == 1234
    with pytest.raises(InvalidInputFormat, match=message):
        setup_factory.dependency_size(_script(modules, files))
