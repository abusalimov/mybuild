"""
Loader for plain old Mybuild files.
"""
from __future__ import absolute_import


__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from myfile import load
from myfile.errors import MyfileError
from myfile.linkage import Linker
from myfile.linkage import FileLinker

from util.importlib.abc import Loader
from util.importlib.machinery import SourceFileLoader

from util.compat import *


class LoaderFileLinker(FileLinker):
    def __init__(self, linker, module):
        super(LoaderFileLinker, self).__init__(linker)
        self.module = module


class MyFileLoader(SourceFileLoader):
    """Loads My-files using myfile parser/linker."""

    MODULE   = 'MYFILE'
    FILENAME = 'Myfile'

    @classmethod
    def init_ctx(cls, ctx, initials):
        return Linker(), dict(initials)

    @classmethod
    def exit_ctx(cls, loader_ctx):
        linker, _ = loader_ctx
        try:
            linker.link_global()
        except MyfileError as e:
            e.print_error()  # TODO bad idea
            raise e

    def __init__(self, loader_ctx, fullname, path):
        super(MyFileLoader, self).__init__(fullname, path)
        self.linker, self.builtins = loader_ctx

    def is_package(self, fullname):
        return False

    def get_code(self, fullname):
        return None

    def _exec_module(self, module):
        fullname = module.__name__

        try:
            result = load(LoaderFileLinker(self.linker, fullname),
                          source=self.get_source(fullname),
                          filename=self.get_filename(fullname),
                          builtins=self.builtins)

        except IOError:
            raise ImportError("IO error while reading a stream")
        except MyfileError as e:
            e.print_error()  # TODO bad idea
            raise e
        else:
            module.__dict__.update(result)


