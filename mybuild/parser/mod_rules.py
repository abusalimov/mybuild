
import types

from mybuild.mybuild import module as mybuild_module, option
from mybuild.mybuild.constraints import Constraints

from mybuild.pybuild.option import Integer, Boolean, List

def package(name):
    import sys
    import build_ctx 

    pkg = build_ctx.root

    for subpkg in name.split('.'):
        if not hasattr(pkg, subpkg):
            setattr(pkg, subpkg, types.ModuleType(subpkg))
        pkg = getattr(pkg, subpkg)

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

def library(name, *args, **kargs):
    module(name, *args, **kargs)

def LDScript(self):
    return self

def Generated(self, fn):
    return self

def NoRuntime(self):
    return self

def DefMacro(macro, src):
    return src

def interface(name, *args, **kargs):
    pass


