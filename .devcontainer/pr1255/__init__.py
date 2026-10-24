"""Upstream PR #1255's PE handler, loaded as an unblob plugin for tests.

FSD §15: L0 foundation this project uses but does not own. The module is the
PR's pe.py at a pinned commit; only its relative imports are made absolute.
Load with `unblob -P /opt/pr1255`.
"""

from unblob.plugins import hookimpl

from .pe import PEHandler


@hookimpl
def unblob_register_handlers():
    return [PEHandler]
