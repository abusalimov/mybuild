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

    def __init__(self, namespace, path, loader_details,
                 package_loader=PackageLoader):
        """
        Args:
            namespace (str): A name of the root package.
            path (Iterable[str]): A list of directories to start searching
                from.
            loader_details (Iterable[(Loader,
                                      Iterable[str],
                                      Mapping[str, Iterable[str]])]): A list of
                tuples of Loader, a list of filename suffixes and a dictionary
                (or a list of pairs) mapping module names to a list of
                filenames.

                Example:

                    [
                        (MyFileLoader, ['.my'], {'MYBUILD': ['Mybuild']}),
                        ...
                    ]

            package_loader (Callable[str, List[str]]): A loader type to use
                to create package loaders. Must accept two positional args:
                    fullname (str): Fully qualified name of a new package
                        module.
                    path (List[str]): Package __path__.
        """
        super(NamespaceFinder, self).__init__()

        self.namespace      = namespace
        self.path           = list(path)
        self.package_loader = package_loader

        self.suffix_loaders          = []  # [('suffix', loader)]
        self.module_filename_loaders = {}  # {'name': [('filename', loader)]}

        for loader, suffixes, module_filenames in loader_details:
            self.suffix_loaders.extend((suffix, loader) for suffix in suffixes)

            for name, filenames in dict(module_filenames).items():
                self.module_filename_loaders.setdefault(name, []) \
                        .extend((filename, loader) for filename in filenames)

    def find_module(self, fullname, path=None):
        """
        Try to find a loader for the specified module.

        Args:
            fullname (str): 'fully.qualified.name'
            path (list or None):
                None - when importing namespace root package
                self.path - importing anything within a namespace package
                pkg.__path__ - within a regular (sub-)package

        Returns:
            A loader if the module has been located, None otherwise.

        For example, to import 'ns.pkg.MYBUILD' inside 'ns', this method gets
        called three times:

            fullname           path           returns
            ----------------   ------------   ----------------------
            'ns'               None           PackageLoader
            'ns.pkg'           self.path      PackageLoader
            'ns.pkg.MYBUILD'   pkg.__path__   MyFileLoader
        """
        namespace, _, restname = fullname.partition('.')

        if namespace != self.namespace:
            return None

        if path is None:
            path = self.path
        if not restname:  # namespace root package
            return self.package_loader(fullname, list(path))

        tailname = restname.rpartition('.')[2]
        try:
            # Explicitly named module, if any
            filename_loaders = self.module_filename_loaders[tailname]
        except KeyError:
            # Regular module, i.e. the name tried with different suffixes
            filename_loaders = [(tailname + suffix, loader)
                                for suffix, loader in self.suffix_loaders]

        for filename, loader_type in filename_loaders:
            for entry in path:
                filepath = os.path.join(entry, filename)
                if os.path.isfile(filepath):
                    return loader_type(fullname, filepath)

        # Namespace packages, i.e. sub-directories
        for entry in path:
            dirpath = os.path.join(entry, tailname)
            if os.path.isdir(dirpath):
                return self.package_loader(fullname, [dirpath])


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
