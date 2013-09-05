"""
Loader for plain old Mybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-05"


from _compat import *

from mylang import my_compile
from mylang import my_exec
from nsloader import pyfile


class MyFileLoader(pyfile.PyFileLoader):
    """Loads My-files using myfile parser/linker."""

    def get_code(self, fullname):
        source_path = self.get_filename(fullname)
        source_string = self.get_source(fullname)

        return my_compile(source_string, source_path, 'exec')

    def _exec_module(self, module):
        my_exec(self.get_code(module.__name__), module.__dict__)

