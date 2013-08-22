"""
Loader for plain old Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from _compat import *

from mylang import my_compile
from mylang import runtime
from nsloader.pyfile import PyFileLoader


class MyFileLoader(PyFileLoader):
    """Loads My-files using myfile parser/linker."""

    MODULE = 'Myfile'

    @classmethod
    def init_ctx(cls, importer, initials):
        exec_ctx = runtime.ProxifyingExecContext()
        builtins = runtime.prepare_builtins(exec_ctx)
        super_ctx = super(MyFileLoader, cls).init_ctx(importer, initials)

        return exec_ctx, builtins, super_ctx

    @classmethod
    def exit_ctx(cls, loader_ctx):
        exec_ctx, _, _ = loader_ctx
        exec_ctx.resolve_all()

    def __init__(self, loader_ctx, fullname, path):
        _, self.builtins, super_ctx = loader_ctx
        super(MyFileLoader, self).__init__(super_ctx, fullname, path)

    def get_code(self, fullname):
        source_path = self.get_filename(fullname)
        source_bytes = self.get_data(source_path)

        return my_compile(source_bytes, source_path, 'exec')

    def _init_module(self, module):
        module.__dict__['__builtins__'] = self.builtins
        super(MyFileLoader, self)._init_module(module)


