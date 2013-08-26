"""
Loader for plain old Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from _compat import *

from mylang import my_compile
from mylang import runtime
from nsloader import pyfile


class MyFileLoader(pyfile.PyFileLoader):
    """Loads My-files using myfile parser/linker."""

    MODULE = 'Myfile'

    def get_code(self, fullname):
        source_path = self.get_filename(fullname)
        source_bytes = self.get_data(source_path)

        return my_compile(source_bytes, source_path, 'exec')

    def _init_module(self, module):
        module.__dict__['__builtins__'] = runtime.builtins
        super(MyFileLoader, self)._init_module(module)

