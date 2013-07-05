"""
Namespace-related loaders that don't run any code directly.
"""

from ..util.importlib.machinery import GenericLoader

from ..util.compat import *


class PackageLoaderBase(GenericLoader):
    """Performs basic initialization required to load a sourceless package."""

    def __init__(self, package_path=None):
        super(PackageLoaderBase, self).__init__()
        if package_path is None:
            package_path = []
        self.path = package_path

    def _init_module(self, module):
        fullname = module.__name__

        module.__file__    = '<mybuild>'
        module.__package__ = fullname
        module.__path__    = self.path
        module.__loader__  = self


class NamespacePackageLoader(PackageLoaderBase):
    """
    Loads package modules corresponding to a namespace being used.

    For example, performing 'my.ns.pkg' import inside 'my.ns' namespace will
    create two modules ('my' and 'my.ns') using this loader.
    """
    def __init__(self):
        super(NamespacePackageLoader, self).__init__()


class SubPackageLoader(PackageLoaderBase):
    """
    Loads sub package modules and fills them by contents of Pybuild or Yaml
    modules.

    This is used to create 'my.ns.pkg' module when importing it within 'my.ns'
    namespace.
    """
    def __init__(self, package_path, sub_module_names):
        super(SubPackageLoader, self).__init__(package_path)
        self._sub_module_names = sub_module_names

    def _init_module(self, module):
        super(SubPackageLoader, self)._init_module(module)

        fullname = module.__name__

        for sub_name in self._sub_module_names:
            try:
                __import__(fullname + '.' + sub_name)
            except ImportError:
                continue

            sub_module = getattr(module, sub_name)

            try:
                attrs = sub_module.__all__
            except AttributeError:
                attrs = [attr for attr in sub_module.__dict__
                         if not attr.startswith('_')]
            for attr in attrs:
                setattr(module, attr, getattr(sub_module, attr))

