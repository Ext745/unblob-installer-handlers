"""unblob handlers for Windows installers and MCU firmware containers.

The composition root (FSD §5): the hooks below are the only place handlers
are wired into unblob.
"""

from unblob.models import Handler
from unblob.plugins import hookimpl

from .dfuse import DfuSeHandler
from .ihex import IntelHexHandler
from .uf2 import UF2Handler

HANDLERS: list[type[Handler]] = [UF2Handler, IntelHexHandler, DfuSeHandler]


@hookimpl
def unblob_register_handlers() -> list[type[Handler]]:
    return HANDLERS
