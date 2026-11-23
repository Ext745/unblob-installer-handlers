"""unblob handlers for Windows installers and MCU firmware containers.

The composition root (FSD §5): the hooks below are the only place handlers
are wired into unblob.
"""

from unblob.models import DirectoryHandler, Handler
from unblob.plugins import hookimpl
from unblob.report import Report

from .dfuse import DfuSeHandler
from .gbl import GblHandler, GblReport
from .ihex import IntelHexHandler
from .inno import InnoSetupHandler
from .installshield import InstallShieldHandler, InstallShieldSetHandler
from .mcuboot import MCUbootHandler, MCUbootImageReport
from .setup_factory import SetupFactoryHandler
from .uf2 import UF2Handler
from .wix_burn import WixBurnHandler
from .zigbee_ota import ZigbeeOtaHandler, ZigbeeOtaReport

HANDLERS: list[type[Handler]] = [
    UF2Handler,
    IntelHexHandler,
    DfuSeHandler,
    MCUbootHandler,
    InstallShieldHandler,
    InnoSetupHandler,
    SetupFactoryHandler,
    WixBurnHandler,
    ZigbeeOtaHandler,
    GblHandler,
]
DIR_HANDLERS: list[type[DirectoryHandler]] = [InstallShieldSetHandler]
REPORTS: list[type[Report]] = [MCUbootImageReport, ZigbeeOtaReport, GblReport]


@hookimpl
def unblob_register_handlers() -> list[type[Handler]]:
    return HANDLERS


@hookimpl
def unblob_register_dir_handlers() -> list[type[DirectoryHandler]]:
    return DIR_HANDLERS


@hookimpl
def unblob_register_reports() -> list[type[Report]]:
    return REPORTS
