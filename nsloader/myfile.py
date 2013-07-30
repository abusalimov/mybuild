"""
Loader for plain old Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from myfile import load
from myfile.errors import MyfileError
from myfile.linkage import Linker

from util.importlib.abc import Loader
from util.importlib.machinery import SourceFileLoader

from util.compat import *


class MybuildFileLoader(SourceFileLoader):
    """Loads Mybuild files."""

    MODULE   = 'MYBUILD'
    FILENAME = 'Mybuild'

    @classmethod
    def init_ctx(cls, ctx, builtins):
        return Linker(), builtins

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

        try:
            result = load(self.linker,
                          source=self.get_source(fullname),
                          filename=self.get_filename(fullname),
                          builtins=self.builtins)

        except IOError:
            raise ImportError("IO error while reading a stream")
        except MyfileError as e:
            e.print_error()  # TODO bad idea
            raise ImportError("Error(s) while parsing/linking a my-file")
        else:
            module.__dict__.update(result)


