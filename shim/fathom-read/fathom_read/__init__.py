"""fathom_read is now right_rudder. This module forwards every import to the new name."""
import importlib
import importlib.abc
import importlib.util
import sys
import warnings

warnings.warn(
    "fathom-read is now right-rudder; install right-rudder and import right_rudder instead of fathom_read",
    DeprecationWarning,
    stacklevel=2,
)

from right_rudder import *  # noqa: F401,F403
from right_rudder import __version__  # noqa: F401


class _Forward(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Resolves fathom_read.<name> to the module right_rudder.<name>."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("fathom_read."):
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        module = importlib.import_module("right_rudder." + spec.name[len("fathom_read."):])
        sys.modules[spec.name] = module
        return module

    def exec_module(self, module):
        return None


sys.meta_path.insert(0, _Forward())
