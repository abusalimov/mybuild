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

    def defaults_for_module(self, module):
        return dict(self.defaults,
                    __builtins__=runtime.builtins,
                    __my_module__=module)

    def get_code(self, fullname):
        source_path = self.get_filename(fullname)
        source_string = self.get_source(fullname)

        return my_compile(source_string, source_path, 'exec')
