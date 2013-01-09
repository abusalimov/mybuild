
import re

from mybuild.package import Package
from module  import Module
from interface import Interface
from scope   import Scope
from domain  import BoolDom
from ops     import *

import logging

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
    return simple_decide(ctx)

def profiling_decide(ctx):
    import cProfile
    return cProfile.runctx('simple_decide(ctx)', globals(), locals())

def simple_decide(ctx):
    scope = ctx.scope

    modlst = map(lambda name: getattr(ctx.root, name), ctx.modlist)

    try:
        add_many(scope, modlst)
    except CutConflictException, e:
        logging.error("%s is empty after all modules adding", e.opt)
        raise

    try:
        cut_scope = cut_many_fancy(scope, lambda mod_name: getattr(ctx.root, mod_name), ctx.modconstr)
    except CutConflictException, e:
        logging.error("%s is in conflict", e.opt)
        raise

    try:
        final = fixate(cut_scope)
    except:
        raise

    return final

def method_define_build(ctx):
    for opt, dom in ctx.model.items():
        opt.build(ctx)


