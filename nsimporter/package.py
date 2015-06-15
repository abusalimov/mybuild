"""
Namespace-related loaders that don't run any code directly.
"""


from _compat import *

import types
from importlib import import_module

from util.importlib.machinery import GenericLoader


class PackageLoader(GenericLoader):
    """Performs basic initialization required to load a sourceless package."""

    DEFAULT_MODULE_TYPE = types.ModuleType

    def __init__(self, fullname, path, module_type=None):
        super(PackageLoader, self).__init__()

        self.name = fullname
        self.path = path

        if module_type is None:
            module_type = self.DEFAULT_MODULE_TYPE
        self.module_type = module_type

    def _new_module(self, fullname):
        return self.module_type(fullname)

    def _init_module(self, module):
        fullname = module.__name__

        module.__file__    = '<nsimporter-package>'
        module.__package__ = fullname
        module.__path__    = self.path
        module.__loader__  = self


class PreloadPackageLoader(PackageLoader):
    """Attempts to load listed modules one by one."""

    def __init__(self, fullname, path, module_type=None, preload_modules=[]):
        super(PreloadPackageLoader, self).__init__(fullname, path,
                                                   module_type=module_type)
        self.preload_modules = list(preload_modules)

    def _init_module(self, module):
        super(PreloadPackageLoader, self)._init_module(module)

        for submodule_name in self.preload_modules:
            try:
                import_module(module.__name__ + '.' + submodule_name)
            except ImportError:
                continue


class TransparentPackageLoader(PreloadPackageLoader):
    """Automatically loads listed modules and also fills the package
    module with public contents of the loaded modules."""

    def _init_module(self, module):
        super(TransparentPackageLoader, self)._init_module(module)

        for submodule_name in self.preload_modules:
            try:
                submodule = getattr(module, submodule_name)
            except AttributeError:
                continue
            for attr, value in iteritems(get_public_exports(submodule)):
                setattr(module, attr, value)


def get_public_exports(module):
    try:
        attrs = module.__all__
    except AttributeError:
        attrs = (attr for attr in module.__dict__
                 if not attr.startswith('_'))
    return dict((attr, getattr(module, attr)) for attr in attrs)


class AutoloadPackageModule(types.ModuleType):
    """In case of missing attribute lookup error attempts to import
    a submodule with such name."""

    def __getattr__(self, name):
        fullname = self.__name__ + '.' + name
        try:
            return import_module(fullname)
        except ImportError:
            raise AttributeError("'{self.__name__}' has no attribute '{name}'"
                                 .format(**locals()))

