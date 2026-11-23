"""Package requirements (FSD §5) checked against the registered handlers."""

from pathlib import Path
from urllib.parse import urlparse

import pytest
from unblob.handlers import BUILTIN_DIR_HANDLERS, BUILTIN_HANDLERS
from unblob.plugins import UnblobPluginManager

PR1255 = Path("/opt/pr1255")

# Our handler names as the FSD and the user manual give them; deliberately not
# read from unblob_installers, so a handler that stops registering is noticed.
OURS = {
    "uf2",
    "ihex",
    "dfuse",
    "mcuboot",
    "installshield",
    "installshield_set",
    "inno",
    "setup_factory",
    "wix_burn",
    "zigbee_ota",
    "gbl",
    "cyacd",
    "cyacd2",
    "nsis",
}


def registered(*paths: Path) -> tuple[list, list]:
    """File and directory handlers unblob loads from plugins.

    That is the unblob_v1 entry point, plus any -P paths given.
    """
    manager = UnblobPluginManager()
    for path in paths:
        manager.import_path(path)
    manager.load_setuptools_entrypoints()
    return (
        manager.load_handlers_from_plugins(),
        manager.load_dir_handlers_from_plugins(),
    )


def test_tc_pkg_03_names_unique_among_all_handlers():
    # FR-PKG-03: with the plugin and #1255 loaded, none of our names may appear
    # twice among all file and directory handlers. unblob's own handlers may
    # share names (26.6.4 has two named "tar").
    if not (PR1255 / "unblob_pr1255" / "__init__.py").is_file():
        pytest.skip("precondition unmet: PR #1255 plugin (pr1255) not installed")
    files, dirs = registered(PR1255)
    names = [h.NAME for h in (*BUILTIN_HANDLERS, *BUILTIN_DIR_HANDLERS, *files, *dirs)]
    assert "pe" in names  # #1255 really loaded
    assert set(names) >= OURS
    assert {n: names.count(n) for n in OURS} == dict.fromkeys(OURS, 1)


def test_tc_pkg_04_every_handler_has_doc_with_references():
    files, dirs = registered()
    handlers = [*files, *dirs]
    assert {h.NAME for h in handlers} == OURS
    for handler in handlers:
        assert handler.DOC is not None, handler.NAME
        assert handler.DOC.references, handler.NAME
        for ref in handler.DOC.references:
            url = urlparse(ref.url)
            assert url.scheme == "https", ref.url
            assert url.netloc, ref.url
