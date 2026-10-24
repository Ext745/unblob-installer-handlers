"""Package requirements (FSD §5) checked against the registered handlers."""

from urllib.parse import urlparse

from unblob.handlers import BUILTIN_HANDLERS

import unblob_installers


def test_tc_pkg_03_names_unique_among_all_handlers():
    # FR-PKG-03: none of our names may appear twice among all handlers.
    # unblob's own handlers may share names (26.6.4 has two named "tar").
    ours = [h.NAME for h in unblob_installers.HANDLERS]
    assert ours
    names = [h.NAME for h in BUILTIN_HANDLERS] + ours
    assert {n: names.count(n) for n in ours} == dict.fromkeys(ours, 1)


def test_tc_pkg_04_every_handler_has_doc_with_references():
    assert unblob_installers.HANDLERS
    for handler in unblob_installers.HANDLERS:
        assert handler.DOC is not None, handler.NAME
        assert handler.DOC.references, handler.NAME
        for ref in handler.DOC.references:
            url = urlparse(ref.url)
            assert url.scheme == "https", ref.url
            assert url.netloc, ref.url
