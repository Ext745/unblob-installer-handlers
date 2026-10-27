"""unblob handlers for Windows installers and MCU firmware containers.

The composition root (FSD §5): the hooks below are the only place handlers
are wired into unblob.
"""

from unblob.models import Handler
from unblob.plugins import hookimpl
from unblob.report import Report

from .dfuse import DfuSeHandler
from .ihex import IntelHexHandler
from .inno import InnoSetupHandler
from .installshield import InstallShieldHandler
from .mcuboot import MCUbootHandler, MCUbootImageReport
from .setup_factory import SetupFactoryHandler
from .uf2 import UF2Handler
from .wix_burn import WixBurnHandler

HANDLERS: list[type[Handler]] = [
    UF2Handler,
    IntelHexHandler,
    DfuSeHandler,
    MCUbootHandler,
    InstallShieldHandler,
    InnoSetupHandler,
    SetupFactoryHandler,
    WixBurnHandler,
]
REPORTS: list[type[Report]] = [MCUbootImageReport]


@hookimpl
def unblob_register_handlers() -> list[type[Handler]]:
    return HANDLERS


@hookimpl
def unblob_register_reports() -> list[type[Report]]:
    return REPORTS
