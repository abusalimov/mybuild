"""
Namespace importer integrated into Python modules infrastructure.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = [
    "NamespaceImportHook",
    "SingleNamespaceImporter",
    "import_all",
]


from _compat import *

import sys
import os.path

from nsimporter.hook import NamespaceImportHook


class SingleNamespaceImporter(NamespaceImportHook):
    """
    PEP 343 context manager.
    """

    def __init__(self, loaders, namespace, path=[]):
        super(SingleNamespaceImporter, self).__init__(loaders,
                                                      {namespace: path})
        self.namespace = namespace

    def register(self):
        if self not in sys.meta_path:
            sys.meta_path.insert(0, self)
        return self

    def unregister(self):
        while self in sys.meta_path:
            sys.meta_path.remove(self)

    def __enter__(self):
        return self.register()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unregister()

    def import_namespace(self):
        return __import__(self.namespace)

    def import_all(self, rel_names=[], silent=False):
        ns = self.namespace
        ns_module = self.import_namespace()  # do it first

        for rel_name in rel_names:
            try:
                __import__(ns + '.' + rel_name)
            except ImportError:
                if not silent:
                    raise

        return ns_module


def import_all(relative_dirnames, loaders, namespace, path=[]):
    """
    Goes through relative_dirnames converting them into module names within
    the specified namespace and importing by using NamespaceImporter.
    """

    with SingleNamespaceImporter(loaders, namespace, path) as importer:
        return importer.import_all(dirname.replace(os.path.sep, '.')
                                   for dirname in relative_dirnames
                                   if '.' not in dirname)

