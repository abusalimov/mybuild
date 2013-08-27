"""
Defines meta hook for importing namespaces.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-06-26"

__all__ = [
    "NamespaceImportHook",
]


from _compat import *

import sys
import os.path

from nsimporter.package import PackageLoader
from util.importlib.abc import MetaPathFinder


class Loader(object):
    """NamespaceImportHook-compatible loader extension protocol.

    This class is mainly serves documentation purposes, there is no need to
    extend it.

    An optional FILENAME attribute is recognized which is used to locate
    a file within directories in a path.
    Defaults to a name inside a loaders mapping of the importer.
    """

    def __init__(self, importer, fullname, path):
        """
        Args:
            importer: an associated importer
            fullname (str): fully.qualified.name of a module to load
            path (str): a file path
        """
        super(Loader, self).__init__()


class NamespaceImportHook(MetaPathFinder):
    """
    PEP 302 meta path import hook.
    """

    def __init__(self, namespace, path=[], loaders=[]):
        super(NamespaceImportHook, self).__init__()

        if '.' in namespace:
            raise NotImplementedError('To keep things simple')

        self.namespace = namespace
        self.path      = list(path)
        self.loaders   = dict(loaders)  # {module_name: loader_type}

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
            'ns.pkg.PYBUILD'   pkg.__path__   PyFileLoader
        """
        namespace, _, restname = fullname.partition('.')

        if namespace != self.namespace:
            return None
        if not restname:
            return PackageLoader(self.path, self.loaders)

        tailname = restname.rpartition('.')[2]
        try:
            loader_type = self.loaders[tailname]

        except KeyError:
            def find_loader_in(entry):
                basepath = os.path.join(entry, tailname)
                if os.path.isdir(basepath):
                    return PackageLoader([basepath], self.loaders)
        else:
            filename = getattr(loader_type, 'FILENAME', tailname)
            def find_loader_in(entry):
                filepath = os.path.join(entry, filename)
                if os.path.isfile(filepath):
                    return loader_type(self, fullname, filepath)

        for loader in map(find_loader_in, path or sys.path):
            if loader is not None:
                return loader

