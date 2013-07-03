"""
Integrates Mybuild-files into Python modules infrastructure by using custom
meta path importer.
"""

import contextlib
import sys
import os.path

from .util.collections import OrderedDict
from .util.importlib.abc import MetaPathFinder
from .util.importlib.machinery import GenericLoader
from .util.importlib.machinery import SourceFileLoader

from .util.compat import *


PYBUILD_MODULE   = 'PYBUILD'
PYBUILD_FILENAME = 'Pybuild'

MYYAML_MODULE   = 'MYYAML'
MYYAML_FILENAME = 'MyYaml'

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


class PackageLoader(GenericLoader):

    def __init__(self, package_path=None):
        super(PackageLoader, self).__init__()
        if package_path is None:
            package_path = []
        self.path = package_path

    def _init_module(self, module):
        fullname = module.__name__

        module.__file__    = '<mybuild>'
        module.__package__ = fullname
        module.__path__    = self.path
        module.__loader__  = self


class NamespacePackageLoader(PackageLoader):
    """
    Loads package modules corresponding to a namespace being used.

    For example, performing 'my.ns.pkg' import inside 'my.ns' namespace will
    create two modules ('my' and 'my.ns') using this loader.
    """

class SubPackageLoader(PackageLoader):
    """
    Loads sub package modules and fills them by contents of Pybuild or Yaml
    modules.

    This is used to create 'my.ns.pkg' module when importing it within 'my.ns'
    namespace.
    """

    def _init_module(self, module):
        super(SubPackageLoader, self)._init_module(module)

        fullname = module.__name__

        for sub_name in PYBUILD_MODULE, MYYAML_MODULE:
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


class PybuildFileLoader(SourceFileLoader):
    """Customization of a Python-like importer.

    Upon creation of a new module initializes its namespace with defaults taken
    from the dictionary passed in __init__. Also adds a global variable
    pointing to a module corresponding to the namespace root.
    """

    def __init__(self, fullname, path, defaults):
        super(PybuildFileLoader, self).__init__(fullname, path)
        self._defaults = defaults

    def _new_module(self, fullname):
        module = super(PybuildFileLoader, self)._new_module(fullname)
        module.__dict__.update(self._defaults)

        namespace_root, dot, _ = fullname.partition('.')
        if dot:
            setattr(module, namespace_root, sys.modules[namespace_root])

        return module

    def is_package(self, fullname):
        return True


class YamlFileLoader(SourceFileLoader):
    def __init__(self, fullname, path, defaults):
        super(YamlFileLoader, self).__init__(fullname, path)
        self._defaults = defaults


class MybuildImporter(MetaPathFinder):

    MODULE_TO_FILE_LOADER = {
        PYBUILD_MODULE: (PYBUILD_FILENAME, PybuildFileLoader),
        MYYAML_MODULE:  (MYYAML_FILENAME, YamlFileLoader),
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
                return NamespacePackageLoader()

            within_namespace = (fullname + '.').startswith(namespace + '.')
            if not within_namespace:
                continue

            tailname = fullname[len(namespace):].rpartition('.')[2]
            try:
                filename, loader_type = self.MODULE_TO_FILE_LOADER[tailname]

            except KeyError:
                def find_loader_in(entry):
                    basepath = os.path.join(entry, tailname)
                    if os.path.isdir(basepath):
                        return SubPackageLoader([basepath])

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


