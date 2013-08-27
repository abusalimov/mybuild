"""
Namespace-related loaders that don't run any code directly.
"""


from _compat import *

import types

from util.importlib.machinery import GenericLoader


class PackageLoader(GenericLoader):
    """Performs basic initialization required to load a sourceless package.

    Also loads modules supported by available loaders and fills the package
    module with public contents of the loaded modules."""

    def __init__(self, path, sub_modules=[]):
        super(PackageLoader, self).__init__()
        self.path = path
        self.sub_modules = sub_modules

    def _new_module(self, fullname):
        return PackageModule(fullname)

    def _init_module(self, module):
        fullname = module.__name__

        module.__file__    = '<nsimporter-package>'
        module.__package__ = fullname
        module.__path__    = self.path
        module.__loader__  = self

        for sub_name in self.sub_modules:
            try:
                __import__(fullname + '.' + sub_name)
            except ImportError:
                continue
            else:
                sub_module = getattr(module, sub_name)

            try:
                attrs = sub_module.__all__
            except AttributeError:
                attrs = [attr for attr in sub_module.__dict__
                         if not attr.startswith('_')]
            for attr in attrs:
                setattr(module, attr, getattr(sub_module, attr))


class PackageModule(types.ModuleType):
    """In case of missing attribute lookup error attempts to import
    a subpackage with such name."""

    def __getattr__(self, name):
        try:
            __import__(self.__name__ + '.' + name)
        except ImportError:
            raise AttributeError("'{cls.__name__}' object has no attribute "
                                 "'{name}'".format(cls=type(self), **locals()))
        else:
            return getattr(self, name)


