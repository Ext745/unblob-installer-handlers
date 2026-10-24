"""TC-PKG-00: the pipeline runs. Asserts no product behaviour."""

from importlib.metadata import entry_points

from unblob.plugins import UnblobPluginManager

import unblob_installers


def test_tc_pkg_00_plugin_loads_through_entry_point():
    (ep,) = [e for e in entry_points(group="unblob_v1") if e.name == "installers"]
    assert ep.load() is unblob_installers

    pm = UnblobPluginManager()
    pm.load_setuptools_entrypoints()
    results = pm.hook.unblob_register_handlers()
    assert unblob_installers.HANDLERS in results
