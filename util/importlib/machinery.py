"""
Machinery: implementations of some finders and loaders.
"""
from __future__ import absolute_import


from _compat import *

import abc
import functools
import imp
import sys
import os.path

from util.importlib import abc as abc_


# Everything below is derived from py3k importlib

class GenericLoader(abc_.Loader):

    def load_module(self, fullname):
        module = sys.modules.get(fullname)

        is_reload = bool(module)
        if not is_reload:
            module = self._new_module(fullname)
            sys.modules[fullname] = module

        try:
            self._init_module(module)
        except:
            if not is_reload:
                del sys.modules[fullname]
            raise

        return module

    def _new_module(self, fullname):
        return imp.new_module(fullname)

    @abc.abstractmethod
    def _init_module(self, module):
        raise NotImplementedError

class SourceLoader(GenericLoader, abc_.SourceLoader):
    """Generic Python source loader."""

    def _init_module(self, module):
        fullname = module.__name__

        module.__file__ = self.get_filename(fullname)
        module.__package__ = fullname
        if self.is_package(fullname):
            module.__path__ = [os.path.dirname(module.__file__)]
        else:
            module.__package__ = module.__package__.rpartition('.')[0]
        module.__loader__ = self

        self._exec_module(module)

    def _exec_module(self, module):
        exec(self.get_code(module.__name__), module.__dict__)

    def is_package(self, fullname):
        """Concrete implementation of InspectLoader.is_package by checking if
        the path returned by get_filename has a filename of '__init__.py'."""
        filename = os.path.split(self.get_filename(fullname))[1]
        filename_base = filename.rsplit('.', 1)[0]
        tail_name = fullname.rpartition('.')[2]
        return filename_base == '__init__' and tail_name != '__init__'


def _check_arg(attr):
    """Deco-maker to verify that the module being requested matches the
    one the loader can handle.

    The first argument (self) must define an attr which the second argument
    is compared against. If the comparison fails then ImportError is
    raised.
    """
    def decorator(fxn):
        @functools.wraps(fxn)
        def decorated(self, arg, *args, **kwargs):
            if getattr(self, attr) != arg:
                raise ImportError("loader for %s %s cannot handle %s" %
                                  (attr, getattr(self, attr), arg))
            return fxn(self, arg, *args, **kwargs)
        return decorated
    return decorator


class FileLoader(abc_.ResourceLoader, abc_.ExecutionLoader):
    """Implements the loader protocol methods that require file system
    usage."""

    def __init__(self, fullname, path):
        """Cache the module name and the path to the file found by the
        finder."""
        super(FileLoader, self).__init__()
        self.name = fullname
        self.path = path

    @_check_arg('name')
    def get_filename(self, fullname):
        """Return the path to the source file as found by the finder."""
        return self.path

    def get_data(self, path):
        """Return the data from path as raw bytes."""
        with open(path, 'rb') as f:
            return f.read()


class SourceFileLoader(FileLoader, SourceLoader):
    """Concrete implementation of SourceLoader using the file system."""

