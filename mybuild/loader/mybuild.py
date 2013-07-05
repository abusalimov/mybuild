"""
Integrates Mybuild-files into Python modules infrastructure by using custom
meta path importer.
"""

import contextlib
import functools
import sys
import os.path

from ..util.importlib.abc import Loader
from ..util.importlib.machinery import SourceFileLoader

from ..util.compat import *


MODULE   = 'MYBUILD'
FILENAME = 'Mybuild'


class MybuildFileLoader(SourceFileLoader):
    """Loads Mybuild files."""

    def __init__(self, fullname, path, defaults):
        super(MybuildFileLoader, self).__init__(fullname, path)

    def is_package(self, fullname):
        return False

    def _init_module(self, module):
        # super(MybuildFileLoader, self)._init_module(module)
        raise NotImplementedError

