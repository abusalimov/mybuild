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

    @property
    def defaults(self):
        return dict(super(MyFileLoader, self).defaults,
                    __builtins__=runtime.builtins)

    def get_code(self, fullname):
        source_path = self.get_filename(fullname)
        source_bytes = self.get_data(source_path)

        return my_compile(source_bytes, source_path, 'exec')

