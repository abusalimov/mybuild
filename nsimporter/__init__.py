"""
Namespace importer integrated into Python modules infrastructure.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"

__all__ = [
    "import_all",
    "using_namespace",
    "normalize_loaders",
    "loader_filenames",
]


import os.path

from .hook import NamespaceImportHook

from util.compat import *


importer_instance = NamespaceImportHook()  # singleton instance

loader_for        = importer_instance.loader_for  # registers a new loader
normalize_loaders = importer_instance.normalize_loaders
loader_filenames  = importer_instance.loader_filenames

using_namespace   = importer_instance.using_namespace


def import_all(relative_dirnames, namespace, path=None, loaders_init=None):
    """
    Goes through relative_dirnames converting them into module names within
    the specified namespace and importing by using importer_instance.
    """

    with using_namespace(namespace, path, loaders_init) as ctx:
        return ctx.import_all(dirname.replace(os.path.sep, '.')
                              for dirname in relative_dirnames
                              if '.' not in dirname)


