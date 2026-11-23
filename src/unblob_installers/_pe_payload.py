"""Base class of the formats packed into or appended to a PE file.

Carries code from onekey-sec/unblob#1255
(https://github.com/onekey-sec/unblob/pull/1255), file
python/unblob/handlers/executable/pe/_payload.py at commit
15e2034a5d63a8e04bc58f9da26156107d9c9bdd, by Jon Crussell (jcrussell) with
Quentin Kaiser (qkaiser); MIT licence, Copyright (c) 2022 ONEKEY GmbH (FSD
D-6, C-12). Changed from that commit only by module renames.
"""

import abc

from unblob.file_utils import File
from unblob.models import Extractor, Reference

from ._pe_headers import PEHeaders


class PEPayload(abc.ABC):
    """Data packed into or appended to a PE file that an external tool unpacks.

    Subclasses detect their format from the parsed headers and return the end of the
    PE including the payload. Each format lives in its own module and is listed in
    ``PAYLOADS`` (pe.py). The handler documentation is assembled from ``description``,
    ``references`` and ``limitations``.
    """

    extractor: Extractor
    # format name, as listed in the handler limitations
    name: str
    # one sentence of the handler description
    description: str
    references: list[Reference]
    limitations: list[str]

    @abc.abstractmethod
    def get_end(self, file: File, headers: PEHeaders, image_end: int) -> int | None:
        """Return the end of the payload relative to the PE start, or None if absent."""
