"""
Defines meta hook for importing namespaces.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-06-26"

__all__ = [
    "NamespaceFinder",
    "NamespaceRouterImportHook",
]


from _compat import *

import os.path

from nsimporter.package import PackageLoader
from util.importlib.abc import MetaPathFinder


class NamespaceFinder(MetaPathFinder):
    """
    PEP 302 meta path import hook.
    """

    def __init__(self, namespace, path, loaders={}):
        super(NamespaceFinder, self).__init__()

        self.namespace = namespace
        self.path      = list(path)
        self.loaders   = dict(loaders) # {module_name: loader}

    def find_module(self, fullname, path=None):
        """
        Try to find a loader for the specified module.

        Args:
            fullname (str): 'fully.qualified.name'
            path (list or None):
                None - when importing namespace root package
                self.path - importing anything within a namespace package
                pkg.__path__ - within a regular (sub-)package;

        Returns:
            A loader if the module has been located, None otherwise.

        For example, to import 'ns.pkg.PYBUILD' inside 'ns', this method gets
        called three times:

            fullname           path           returns
            ----------------   ------------   ----------------------
            'ns'               None           PackageLoader
            'ns.pkg'           self.path      PackageLoader
            'ns.pkg.Pybuild'   pkg.__path__   PyFileLoader
        """
        namespace, _, restname = fullname.partition('.')

        if namespace != self.namespace:
            return None

        if path is None:
            path = self.path
        if not restname:  # namespace root package
            return PackageLoader(path, self.loaders)

        tailname = restname.rpartition('.')[2]
        try:
            loader_type = self.loaders[tailname]

        except KeyError:  # is it a sub-package?
            def find_loader_in(entry):
                basepath = os.path.join(entry, tailname)
                if os.path.isdir(basepath):
                    return PackageLoader([basepath], self.loaders)

        else:  # found a module loader, is there a corresponding file?
            filename = getattr(loader_type, 'FILENAME', tailname)
            def find_loader_in(entry):
                filepath = os.path.join(entry, filename)
                if os.path.isfile(filepath):
                    return loader_type(fullname, filepath)

        for loader in map(find_loader_in, path):
            if loader is not None:
                return loader


class NamespaceRouterImportHook(MetaPathFinder):
    """PEP 302 meta path import hook that routes find requests to a
    NamespaceFinder register for a given namespace.
    """

    def __init__(self, namespace_map={}):
        super(NamespaceRouterImportHook, self).__init__()
        self.namespace_map = dict(namespace_map)

    def find_module(self, fullname, path=None):
        namespace = fullname.partition('.')[0]
        try:
            finder = self.namespace_map[namespace]
        except KeyError:
            return None
        else:
            return finder.find_module(fullname, path)
