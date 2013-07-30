"""
Python-like loader which is able to customize default global namespace.
"""

import sys

from util.importlib.machinery import SourceFileLoader
from util.compat import *


class PyFileLoader(SourceFileLoader):
    """Loads Pybuild files and executes them as regular Python scripts.

    Upon creation of a new module initializes its namespace with defaults taken
    from the dictionary passed in __init__. Also adds a global variable
    pointing to a module corresponding to the namespace root.
    """

    MODULE   = 'PYBUILD'
    FILENAME = 'Pybuild'

    @classmethod
    def init_ctx(cls, ctx, initials):
        return initials  # defaults

    def __init__(self, defaults, fullname, path):
        super(PyFileLoader, self).__init__(fullname, path)
        self.defaults = dict(defaults)

    def is_package(self, fullname):
        return False

    def _init_module(self, module):
        fullname = module.__name__

        module.__dict__.update(self.defaults)

        namespace_root, dot, _ = fullname.partition('.')
        if dot:
            setattr(module, namespace_root, sys.modules[namespace_root])

        super(PyFileLoader, self)._init_module(module)

