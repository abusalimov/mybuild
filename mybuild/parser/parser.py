
__author__ = "Anton Kozlov"
__date__ = "2012-12-12"

from mybuild.common import pkg

from mybuild.mybuild import module as mybuild_module

import types

def root_pkg():
    return types.ModuleType('root')

def prepare_build(root):
    def content_fn(pkg):
	return [(name if not isinstance(obj, types.ModuleType) else obj.__name__, obj) 
		for name, obj in pkg.__dict__.items()]
    modlist = pkg.modlist(root, types.ModuleType, mybuild_module, content_fn)
    print '\n'.join(modlist)
    return modlist
