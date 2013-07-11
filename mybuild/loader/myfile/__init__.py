"""
Loader for plain old Mybuild files.
"""

from .. import mybuild_importer

from ...util.importlib.abc import Loader
from ...util.importlib.machinery import SourceFileLoader

from ...util.compat import *

try:
    import ply
except ImportError:
    ply = None


FILENAME = 'Mybuild'

@mybuild_importer.loader_for(FILENAME)
class MybuildFileLoader(SourceFileLoader):
    """Loads Mybuild files."""

    def __init__(self, ctx, fullname, path):
        super(MybuildFileLoader, self).__init__(fullname, path)

    def is_package(self, fullname):
        return False

