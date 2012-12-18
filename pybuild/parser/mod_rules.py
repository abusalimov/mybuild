
from .. package import Package, obj_in_pkg
from .. module  import Module
from .. interface import Interface
from .. option import *

from mybuild.source import LDScript, Generated, NoRuntime, Source, StaticSource

def package(name):
    global package_name
    package_name = name

    import build_ctx
    ctx = build_ctx

    ctx.root.built_subpack(name)


def _build_obj(cls, name, args, kargs):
    global package_name
    
    import build_ctx
    ctx = build_ctx
    ctx.modlist.append('.'.join ((package_name, name)))
    obj_in_pkg(cls, ctx.root[package_name], name, *args, **kargs)

def module(name, *args, **kargs):
    import build_ctx
    ctx = build_ctx
    if kargs.has_key('sources'):
	kargs['sources'] = map (lambda s: Source(ctx.dirname, s), kargs['sources'])
    _build_obj(Module, name, args, kargs)

def interface(name, *args, **kargs):
    _build_obj(Interface, name, args, kargs)

def library(name, *args, **kargs):
    import build_ctx
    ctx = build_ctx
    if kargs.has_key('sources'):
	kargs['sources'] = map (lambda s: StaticSource(ctx.dirname, s), kargs['sources'])
    _build_obj(Module, name, args, kargs)

