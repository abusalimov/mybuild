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

    @classmethod
    def init_ctx(cls, ctx, initials):
        return None  # FIXME linker object

    @classmethod
    def exit_ctx(cls, linker):
        pass  # invoke global linkage here

    def __init__(self, linker, fullname, path):
        super(MybuildFileLoader, self).__init__(fullname, path)
        self.linker = linker

    def is_package(self, fullname):
        return False

    def get_code(self, fullname):
        return None

    def _exec_module(self, module):
        if ply is None:
            raise ImportError('PLY is not installed')

        try:
            result = parse(self.get_source(module.__name__))

        except IOError:
            raise ImportError("IO error while reading a stream")
        except SyntaxError:
            raise

        else:
            print result
            self._link_module(module, result)

    def _link_module(self, module, result):
        self.linker  # TODO tell linker about a new module



