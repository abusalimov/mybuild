"""
Integrates Mybuild-files into Python modules infrastructure by using custom
meta path importer.
"""

import contextlib
import functools
import sys
import os.path

from . import my_yaml
from . import mybuild
from . import pybuild
from . import package

from ..util.collections import OrderedDict
from ..util.importlib.abc import MetaPathFinder

from ..util.compat import *


def import_all(ctx, relative_dirnames, namespace, path=None, defaults=None):
    """
    Goes through relative_dirnames converting them into module names within
    the specified namespace and importing by using mybuild_importer.
    """

    with mybuild_importer.using_namespace(namespace, path, defaults):
        for dirname in relative_dirnames:
            if '.' not in dirname:
                __import__(namespace + '.' + dirname.replace(os.path.sep, '.'))

        return __import__(namespace)


class MybuildImporter(MetaPathFinder):

    MODULE_MAP = {
        my_yaml.MODULE: (my_yaml.FILENAME, my_yaml.MyYamlFileLoader),
        mybuild.MODULE: (mybuild.FILENAME, mybuild.MybuildFileLoader),
        pybuild.MODULE: (pybuild.FILENAME, pybuild.PybuildFileLoader),
    }

    def __init__(self):
        super(MybuildImporter, self).__init__()
        self._namespaces = OrderedDict()

    def find_module(self, fullname, package_path=None):
        """
        Try to find a loader for the specified module.

        Args:
            fullname (str): 'fully.qualified.name'
            package_path:
                None   - when importing root package;
                []     - importing anything within a namespace package;
                [path] - within a regular (sub-)package;

        Returns:
            A loader if the module has been located, None otherwise.

        For example, to import 'my.ns.pkg.PYBUILD' inside 'my.ns', this method
        is called four times:

            fullname              package_path   returns
            -------------------   ------------   ----------------------
            'my'                  None           NamespacePackageLoader
            'my.ns'               []             NamespacePackageLoader
            'my.ns.pkg'           []             SubPackageLoader
            'my.ns.pkg.PYBUILD'   [path]         PybuildFileLoader

        """

        for namespace, (path, defaults) in iteritems(self._namespaces):

            is_namespace_package = (namespace + '.').startswith(fullname + '.')
            if is_namespace_package:
                return package.NamespacePackageLoader()

            within_namespace = (fullname + '.').startswith(namespace + '.')
            if not within_namespace:
                continue

            tailname = fullname[len(namespace):].rpartition('.')[2]
            try:
                filename, loader_type = self.MODULE_MAP[tailname]

            except KeyError:
                def find_loader_in(entry):
                    basepath = os.path.join(entry, tailname)
                    if os.path.isdir(basepath):
                        return package.SubPackageLoader([basepath],
                                                        list(self.MODULE_MAP))

            else:
                def find_loader_in(entry):
                    filepath = os.path.join(entry, filename)
                    if os.path.isfile(filepath):
                        return loader_type(fullname, filepath, defaults)

            if package_path:
                path = package_path

            elif not path:
                path = sys.path

            for loader in map(find_loader_in, path):
                if loader is not None:
                    return loader

    @contextlib.contextmanager
    def using_namespace(self, namespace, path=None, defaults=None):
        saved = self.register_namespace(namespace, path, defaults)
        try:
            yield
        finally:
            if saved is not None:
                self.register_namespace(namespace, *saved)
            else:
                self.unregister_namespace(namespace)

    def register_namespace(self, namespace, path=None, defaults=None):
        defaults = dict(defaults) if defaults is not None else {}
        path     = list(path)     if path     is not None else []

        was_empty = not self._namespaces
        prev = self._namespaces.get(namespace)

        self._namespaces[namespace] = (path, defaults)

        if was_empty and self not in sys.meta_path:
            sys.meta_path.insert(0, self)

        return prev

    def unregister_namespace(self, namespace):
        del self._namespaces[namespace]

        if not self._namespaces and self in sys.meta_path:
            sys.meta_path.remove(self)


mybuild_importer = MybuildImporter()  # singleton instance


