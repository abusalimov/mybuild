"""
Loader for plain old Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from .linkage import GlobalLinker
from .linkage import LocalLinker
try:
    from .parse import parse
except ImportError:
    parse = None

from .. import mybuild_importer

from ...util.importlib.abc import Loader
from ...util.importlib.machinery import SourceFileLoader

from ...util.compat import *


LOADER_NAME = 'MYBUILD'

@mybuild_importer.loader_for(LOADER_NAME)
class MybuildFileLoader(SourceFileLoader):
    """Loads Mybuild files."""

    FILENAME = 'Mybuild'

    @classmethod
    def init_ctx(cls, ctx, builtins):
        return GlobalLinker(), builtins

    @classmethod
    def exit_ctx(cls, ctx):
        linker, _ = ctx
        linker.link_global()

    def __init__(self, ctx, fullname, path):
        super(MybuildFileLoader, self).__init__(fullname, path)
        self.linker, self.builtins = ctx

    def is_package(self, fullname):
        return False

    def get_code(self, fullname):
        return None

    def _exec_module(self, module):
        if parse is None:
            raise ImportError('PLY is not installed')

        local_linker = LocalLinker(self.linker)

        try:
            result = parse(self.get_source(module.__name__),
                           linker=local_linker, builtins=self.builtins)

        except IOError:
            raise ImportError("IO error while reading a stream")
        except SyntaxError:
            raise

        local_linker.link_local()

        ast_root, global_scope = result
        module.__dict__.update(global_scope)


