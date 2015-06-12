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
from util.misc import conv, conv_args


class NamespaceFinder(MetaPathFinder):
    """
    PEP 302 meta path import hook.
    """

    @conv_args(path=['entry'],
               suffix_loaders=[('suffix', callable)],
               module_filename_loaders={'name': [('filename', callable)]})
    def __init__(self, namespace, path,
                 suffix_loaders, module_filename_loaders):
        """
        Args:
            namespace (str): A name of the root package.
            path (Iterable[str]): A list of directories to start searching
                from.
        """
        super(NamespaceFinder, self).__init__()

        self.namespace = namespace
        self.path      = path

        self.suffix_loaders          = suffix_loaders
        self.module_filename_loaders = module_filename_loaders

    @classmethod
    @conv_args(loader_details=[(callable, ['suffix'], {'name': ['filename']})])
    def from_details(cls, namespace, path, loader_details):
        """
        An alternative constructor.

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
        """

        suffix_loaders          = []  # [('suffix', loader)]
        module_filename_loaders = {}  # {'name': [('filename', loader)]}

        for loader, suffixes, module_filenames in loader_details:
            suffix_loaders.extend((suffix, loader) for suffix in suffixes)

            for name, filenames in module_filenames.items():
                module_filename_loaders.setdefault(name, []) \
                        .extend((filename, loader) for filename in filenames)

        return cls(namespace, path, suffix_loaders, module_filename_loaders)

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
            return PackageLoader(path, self.module_filename_loaders)

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
                return PackageLoader([dirpath], self.module_filename_loaders)


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
