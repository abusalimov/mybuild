"""
Namespace importer integrated into Python modules infrastructure.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = [
    "import_all",
    "loader_module",
    "loader_filename",
]


from _compat import *

import os.path

from nsimporter.hook import loader_module
from nsimporter.hook import loader_filename
from nsimporter.hook import NamespaceContextManager


class NamespaceImporter(NamespaceContextManager):

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


def import_all(relative_dirnames, namespace, path=None, loaders_init=None):
    """
    Goes through relative_dirnames converting them into module names within
    the specified namespace and importing by using NamespaceImporter.
    """

    with NamespaceImporter(namespace, path, loaders_init) as importer:
        return importer.import_all(dirname.replace(os.path.sep, '.')
                                   for dirname in relative_dirnames
                                   if '.' not in dirname)

