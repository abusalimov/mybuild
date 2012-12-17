
import re

from package import Package
from module  import Module
from interface import Interface
from scope   import Scope
from domain  import BoolDom
from ops     import *

from mybuild.build import inchdr

def method_pre_parse(ctx):
    ctx.scope = Scope()
    ctx.root = Package('root', None)
    ctx.modlist = []
    ctx.modconstr = []
    ctx.ld_defs = []

    return ctx

def method_decide_build(ctx):
    scope = ctx.scope

    modlst = map(lambda name: ctx.root[name], ctx.modlist)

    add_many(scope, modlst)

    modconstr = map(lambda (name, dom): (ctx.root[name], dom), ctx.modconstr)

    cut_scope = cut_many(scope, modconstr)

    final = fixate(cut_scope)

    return final

def method_define_build(bld, model):
    for opt, dom in model.items():
	need_header = False
	header_inc = []
	header_opts = []

	if isinstance(opt, Interface):
	    need_header |= True
	    for impl in model[opt]:
		for src in impl.sources:
		    if re.match('.*\.h', src.filename):
			header_inc.append(src.fullpath())

	if (isinstance(opt, Module) and dom == BoolDom([True])):
	    need_header |= True

	    for name, var in opt.items():
		repr = var.build_repr()
		if not repr:
		    continue
	        header_opts.append(inchdr(repr, opt.qualified_name(), name, model[var].value()))

	    for src in opt.sources:
		src.build(bld, opt, model) 

	if need_header:
	    bld(features = 'module_header',
		mod_name = opt.qualified_name(),
		header_opts = header_opts,
		header_inc = header_inc)


