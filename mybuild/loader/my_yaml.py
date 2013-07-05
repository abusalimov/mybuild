"""
Integrates Mybuild-files into Python modules infrastructure by using custom
meta path importer.
"""

import contextlib
import functools
import sys
import os.path

from ..util.importlib.abc import Loader
from ..util.importlib.machinery import SourceFileLoader

from ..util.compat import *


MODULE   = 'MYYAML'
FILENAME = 'MyYaml'


try:
    import yaml

except ImportError:
    class MyYamlFileLoader(Loader):
        def load_module(self, fullname):
            raise ImportError('PyYaml is not installed')

else:
    try:
        from yaml import CLoader as YamlLoader
    except ImportError:
        from yaml import YamlLoader

    class MyYamlFileLoader(SourceFileLoader):
        """Loads YAML files using PyYaml library."""

        def __init__(self, fullname, path, defaults):
            super(MyYamlFileLoader, self).__init__(fullname, path)
            self._defaults = dict((key, value)
                                  for key, value in iteritems(defaults)
                                  if key[0] == '!')

        def is_package(self, fullname):
            return False

        def get_code(self, fullname):
            return None

        def _exec_module(self, module):
            fullname = module.__name__

            class MyYamlLoader(YamlLoader):
                pass

            for tag, func in iteritems(self._defaults):
                @functools.wraps(func)
                def constructor(loader, node):
                    return func(fullname, loader.construct_mapping(node))

                yaml.add_constructor(tag, constructor, Loader=MyYamlLoader)

            try:
                stream = file(self.get_filename(fullname), 'r')
                docs = yaml.load_all(stream, Loader=MyYamlLoader)

            except IOError:
                raise ImportError("IO error while reading a stream")
            except yaml.YamlError as e:
                raise e  # XXX convert into SyntaxError

            else:
                for doc in docs:
                    if not hasattr(doc, '__name__'):
                        continue
                    setattr(module, doc.__name__, doc)

