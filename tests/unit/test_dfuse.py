"""DfuSe pure core (FSD §12): element file naming."""

import importlib
from types import ModuleType

import pytest


def dfuse() -> ModuleType:
    # Imported per test, so the file is collected before the module exists.
    return importlib.import_module("unblob_installers.dfuse")


@pytest.mark.xfail(reason="FR-DFU-05: dfuse handler absent", strict=True)
def test_tc_dfu_05_element_path():
    path = dfuse().element_path
    assert str(path(0, b"Internal Flash\0\0\0", 0x08000000)) == (
        "target0_Internal_Flash/0x08000000.bin"
    )
    assert str(path(1, None, 0x1FFF7800)) == "target1_unnamed/0x1fff7800.bin"
