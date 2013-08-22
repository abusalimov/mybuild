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

    MODULE = 'Pyfile'

    @classmethod
    def init_ctx(cls, importer, initials):
        return importer.namespace, dict(initials)  # defaults

    def __init__(self, loader_ctx, fullname, path):
        super(PyFileLoader, self).__init__(fullname, path)
        self.namespace, self.defaults = loader_ctx

    def is_package(self, fullname):
        return False

    def _init_module(self, module):
        module.__dict__[self.namespace] = __import__(self.namespace)
        module.__dict__.update(self.defaults)

        super(PyFileLoader, self)._init_module(module)

