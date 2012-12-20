
from .. package import Package, obj_in_pkg
from .. module  import Module
from .. interface import Interface
from .. option import *

from mybuild.source     import Source
from mybuild.annotation import LDScript, Generated, NoRuntime, DefMacro, IncludePath

from .. util import isvector

def package(name):
    global package_name
    package_name = name

    import build_ctx
    ctx = build_ctx

    ctx.pkglist.add(ctx.root.built_subpack(name))

def __build_obj(cls, name, args, kargs):
    global package_name
    
    import build_ctx
    ctx = build_ctx
    ctx.modlist.append('.'.join ((package_name, name)))
    return obj_in_pkg(cls, ctx.root[package_name], name, *args, **kargs)

def __process(kargs, fn, key):
    import build_ctx
    ctx = build_ctx
    def psrc(s):
        return Source(ctx.dirname, s)
    if kargs.has_key(key):
        flat = []
        for o in kargs[key]:
            if isvector(o):
                flat += [fn(obj) for obj in o]
            else:
                flat.append(fn(o))
        kargs[key] = flat
        

def __mod(cls, name, args, kargs):
    import build_ctx
    ctx = build_ctx
    __process(kargs, lambda s: Source(ctx.dirname, s), 'sources')
    __process(kargs, lambda s: s, 'depends')
    return __build_obj(cls, name, args, kargs)

def module(name, *args, **kargs):
    return __mod(Module, name, args, kargs)

def interface(name, *args, **kargs):
    __build_obj(Interface, name, args, kargs)

def library(name, *args, **kargs):
    kargs['static'] = True
    return __mod(Module, name, args, kargs)

def runlevel(n, depends=[]):
    import build_ctx
    ctx = build_ctx
    ctx.runlevels[n] = __build_obj(Module, 'runlevel%d' % (n,), [], {'depends' : depends})
