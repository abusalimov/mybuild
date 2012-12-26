
import re

from package import Package
from module  import Module
from interface import Interface
from scope   import Scope
from domain  import BoolDom
from ops     import *

def method_pre_parse(ctx):
    ctx.scope = Scope()
    ctx.root = Package('root', None)
    ctx.modlist = []
    ctx.pkglist = set()
    ctx.modconstr = []
    ctx.ld_defs = []
    ctx.runlevels = {}

    return ctx

def method_decide_build(ctx):
    scope = ctx.scope

    modlst = map(lambda name: ctx.root[name], ctx.modlist)

    add_many(scope, modlst)

    cut_scope = cut_many_fancy(scope, lambda mod_name: ctx.root[mod_name], ctx.modconstr)

    final = fixate(cut_scope)

    return final

def method_define_build(ctx):
    for opt, dom in ctx.model.items():
        opt.build(ctx)


