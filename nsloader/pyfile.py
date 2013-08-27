"""
Python-like loader which is able to customize default global namespace.
"""


from _compat import *

from util.importlib.machinery import SourceFileLoader


class PyFileLoader(SourceFileLoader):
    """Loads Pybuild files and executes them as regular Python scripts.

    Upon creation of a new module initializes its namespace with defaults taken
    from the dictionary passed in __init__. Also adds a global variable
    pointing to a module corresponding to the namespace root.
    """

    @property
    def defaults(self):
        namespace = self.importer.namespace
        return {namespace: __import__(namespace)}

    def __init__(self, importer, fullname, path):
        super(PyFileLoader, self).__init__(fullname, path)
        self.importer = importer

    def is_package(self, fullname):
        return False

    def _init_module(self, module):
        module.__dict__.update(self.defaults)
        super(PyFileLoader, self)._init_module(module)

