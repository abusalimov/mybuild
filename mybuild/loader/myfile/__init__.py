"""
Loader for plain old Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from .errors import MyfileError
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
        try:
            linker.link_global()
        except MyfileError as e:
            e.print_error()  # TODO bad idea
            raise ImportError("Error(s) while linking all my-files")

    def __init__(self, ctx, fullname, path):
        super(MybuildFileLoader, self).__init__(fullname, path)
        self.linker, self.builtins = ctx

    def is_package(self, fullname):
        return False

    def get_code(self, fullname):
        return None

    def _exec_module(self, module):
        fullname = module.__name__

        if parse is None:
            raise ImportError('PLY is not installed')

        try:
            local_linker = LocalLinker(self.linker)
            result = parse(self.get_source(fullname),
                           linker=local_linker, builtins=self.builtins,
                           filename=self.get_filename(fullname))

            local_linker.link_local()

        except IOError:
            raise ImportError("IO error while reading a stream")
        except MyfileError as e:
            e.print_error()  # TODO bad idea
            raise ImportError("Error(s) while parsing/linking a my-file")
        else:
            ast_root, global_scope = result
            module.__dict__.update(global_scope)


