"""
Mybuild tool for Waf.
"""

import abc
import functools
import imp
import sys
import os

from compat import *

from util import OrderedDict

from waflib import Context as wafcontext
from waflib import Utils   as wafutils

def options(ctx):
    print('mywaf: %r' % ctx)

def configure(ctx):
    print('mywaf: %r' % ctx)

def load_myfiles(ctx, myfile_names, root_node=None):
    if root_node is None:
        root_node = ctx.path
    myfiles_glob = ['**/' + f for f in wafutils.to_list(myfile_names)]
    files = root_node.ant_glob(myfiles_glob)
    print files

wafcontext.Context.load_myfiles = load_myfiles

# Everything below is derived from py3k importlib.

class SourceLoader(object):
    """Generic Python source loader."""
    __metaclass__ = abc.ABCMeta

    def load_module(self, name):
        module = sys.modules.get(name)

        is_reload = bool(module)
        if not is_reload:
            module = self._new_module(name)
            sys.modules[name] = module

        try:
            self._init_module(module)
        except:
            if not is_reload:
                del sys.modules[name]
            raise

        return module

    def _new_module(self, name):
        return imp.new_module(name)

    def _init_module(self, module):
        name = module.__name__
        code_object = self.get_code(name)

        module.__file__ = self.get_filename(name)
        module.__package__ = name
        if self.is_package(name):
            module.__path__ = self._get_path_list(module.__file__)
        else:
            module.__package__ = module.__package__.rpartition('.')[0]
        module.__loader__ = self

        exec(code_object, module.__dict__)

    def is_package(self, name):
        """Everything is assumed to be a package. No modules."""
        return True

    def get_source(self, name):
        """Concrete implementation of InspectLoader.get_source."""
        path = self.get_filename(name)
        try:
            source_bytes = self.get_data(path)
        except IOError:
            raise ImportError("source not available through get_data()")
        return source_bytes.decode(encoding[0])

    def get_code(self, name):
        """Reads a source using Loader.get_data and returns complied code. """
        source_path = self.get_filename(name)
        source_bytes = self.get_data(source_path)
        code_object = compile(source_bytes, source_path, 'exec',
                                dont_inherit=True)
        return code_object

    @abc.abstractmethod
    def get_filename(self, name):
        raise NotImplementedError
    @abc.abstractmethod
    def get_data(self, path):
        raise NotImplementedError
    @abc.abstractmethod
    def _get_path_list(self, filename):
        raise NotImplementedError


def _check_arg(attr):
    """Deco-maker to verify that the module being requested matches the
    one the loader can handle.

    The first argument (self) must define an attr which the second argument
    is compared against. If the comparison fails then ImportError is
    raised.
    """
    def decorator(fxn):
        @functools.wraps(fxn)
        def decorated(self, arg, *args, **kwargs):
            if getattr(self, attr) != arg:
                raise ImportError("loader for %s %s cannot handle %s" %
                                  (attr, getattr(self, attr), arg))
            return fxn(self, arg, *args, **kwargs)
        return decorated
    return decorator


class FileLoader(object):

    """Base file loader class which implements the loader protocol methods that
    require file system usage."""

    def __init__(self, name, filename):
        """Cache the module name and the path to the file found by the
        finder."""
        super(FileLoader, self).__init__()
        self._name = name
        self._filename = filename

    @_check_arg('_name')
    def get_filename(self, name):
        """Return the path to the source file as found by the finder."""
        return self._filename

    @_check_arg('_filename')
    def get_data(self, filename):
        """Return the data from path as raw bytes."""
        with open(filename, 'rb') as f:
            return f.read()

    @_check_arg('_filename')
    def _get_path_list(self, filename):
        return [os.path.dirname(filename)]


class SourceFileLoader(FileLoader, SourceLoader):
    """Concrete implementation of SourceLoader using the file system."""

class MybuildFileLoader(SourceFileLoader):
    """docstring for MybuildFileLoader"""

    def __init__(self, name, filename, defaults):
        super(MybuildFileLoader, self).__init__(name, filename)
        self._defaults = defaults

    def _new_module(self, name):
        module = super(MybuildFileLoader, self)._new_module(name)
        module.__dict__.update(self._defaults)
        return module

    @_check_arg('_filename')
    def _get_path_list(self, filename):
        return []  # our finder ignores it anyway


class MyFileFinder(object):

    MYBUILD_FILENAME = 'Pybuild'

    def __init__(self):
        super(MyFileFinder, self).__init__()
        self._namespaces = OrderedDict()

    def find_module(self, name, ignored_path=None):
        """Try to find a loader for the specified 'fully.qualified.name'."""

        for namespace, (path, defaults) in iteritems(self._namespaces):
            print '>>>', name, namespace, path, defaults

            if not name.startswith(namespace):
                continue

            restname = name[len(namespace):]
            if restname and namespace[-1] != '.' != restname[0]:
                continue

            if restname and restname[0] == '.':
                restname = restname[1:]

            if path is None:
                path = sys.path

            for entry in path:
                filename = self._find_mybuild(restname, entry)
                print '>>> >>>', restname, entry, ':', filename
                if filename:
                    return MybuildFileLoader(name, filename, defaults)

    def _find_mybuild(self, restname, path):
        basepath = os.path.join(path, *restname.split('.'))
        if os.path.isdir(basepath):
            filename = os.path.join(basepath, self.MYBUILD_FILENAME)
            if os.path.isfile(filename):
                return filename

    def register_namespace(self, namespace, path=None, default_globals=None):
        was_empty = not self._namespaces

        defaults = dict(default_globals) if default_globals is not None else {}
        if path is not None: path = list(path)

        self._namespaces[namespace] = (path, default_globals)

        if was_empty and self not in sys.meta_path:
            sys.meta_path.insert(0, self)

    def unregister_namespace(self, namespace):
        del self._namespaces[namespace]

        if not self._namespaces and self in sys.meta_path:
            sys.meta_path.remove(self)


my_file_importer = MyFileFinder()  # singleton instance


