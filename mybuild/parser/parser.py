
__author__ = "Anton Kozlov"
__date__ = "2012-12-12"

from mybuild import module as mybuild_module, option
from mybuild.constraints import Constraints

from pybuild.option import Integer, Boolean, List

import common.pkg

import types

def LDScript(self):
    return self

def Generated(self, fn):
    return self

def NoRuntime(self):
    return self

def interface(name, *args, **kargs):
    pass

def root_pkg():
    return types.ModuleType('root')

def package(name):
    import sys
    import config

   
    pkg = config.root

    for subpkg in name.split('.'):
	if not hasattr(pkg, name):
	    pkg.__dict__[name] = types.ModuleType(subpkg)
	pkg = getattr(pkg, name)

    global this_pkg
    this_pkg = pkg

def module(name, *args, **kargs):
    def convert_opt(opt):
	return '%s = option()' % (opt.name)
    opts = ', '.join(map(lambda o: convert_opt(o), kargs.get('options', [])))
    fn_decl = '''
@mybuild_module
def {MOD_NAME}(self, {OPTIONS}):
    pass
    '''.format(MOD_NAME=name, OPTIONS = opts)

    exec fn_decl in globals(), locals()

    this_pkg.__dict__[name] = locals()[name]

def prepare_build(root):
    def content_fn(pkg):
	return [(name if not isinstance(obj, types.ModuleType) else obj.__name__, obj) 
		for name, obj in pkg.__dict__.items()]
    modlist = common.pkg.modlist(root, types.ModuleType, mybuild_module, content_fn)
    print '\n'.join(modlist)
    return modlist
