"""Package requirements (FSD §5) checked against the registered handlers."""

from urllib.parse import urlparse

import pytest
from unblob.handlers import BUILTIN_HANDLERS

import unblob_installers

needs_a_handler = pytest.mark.xfail(
    not unblob_installers.HANDLERS, reason="no handler registered yet", strict=True
)


@needs_a_handler
def test_tc_pkg_03_names_unique_among_all_handlers():
    ours = [h.NAME for h in unblob_installers.HANDLERS]
    assert ours
    names = [h.NAME for h in BUILTIN_HANDLERS] + ours
    assert len(names) == len(set(names))


@needs_a_handler
def test_tc_pkg_04_every_handler_has_doc_with_references():
    assert unblob_installers.HANDLERS
    for handler in unblob_installers.HANDLERS:
        assert handler.DOC is not None, handler.NAME
        assert handler.DOC.references, handler.NAME
        for ref in handler.DOC.references:
            url = urlparse(ref.url)
            assert url.scheme == "https", ref.url
            assert url.netloc, ref.url
