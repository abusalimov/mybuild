
import itertools

from exception import *

import option
import domain
import scope

from util import isvector

from ops  import *

import common.repr

def trigger_handle(cont, scope, trig, *args, **kwargs):
    opt = None
    try:
	trig_ret = trig(scope, *args, **kwargs)

	if isinstance(trig_ret, Scope):
	    return cont(trig_ret)

	return cont(scope)
    except MultiValueException, excp:
	opt = excp.opt

    dom = scope[opt]

    if hasattr(opt, 'default') and opt.default in dom:
	dom = itertools.chain((opt.default,), dom)

    for value in dom:
	value_scope = cut(scope, opt, opt.domain_class([value]))

	try:
	    return trigger_handle(cont, value_scope, trig, *args, **kwargs)
	except CutConflictException or MultiValueException, excp:
	    pass

    raise CutConflictException(opt)

class Module(option.Boolean, scope.BaseScope):
    def __init__(self, name, pkg=None, sources=[], options=[], super=None, implements=(), depends=(), include_trigger=None):
	option.Boolean.__init__(self, name, pkg = pkg)
	self.parent = super
	self.name = name
	self.include_trigger = include_trigger
	self.sources = sources

	self.options = []
	self.options += options
	self.hash_value = hash(name + '.include_module')

	self.depends = []

	for d in depends:
	    if not isvector(d):
		self.depends.append((d, {}))
	    else:
		self.depends.append(d)

	self.implements = implements

	for o in self.options:
	    o.pkg = self
	    self[o.name] = o

    def add_trigger(self, scope):
	for impl in self.implements:
	    implmod = self.pkg.root().find_with_imports([self.pkg.qualified_name(), ''], impl)
	    scope[implmod] |= domain.ModDom([self])
	return scope

    def cut_trigger(self, cont, scope, old_domain):
	dom = scope[self]
	v = dom.value()
	if len(dom) > 1: 
	    return cont(scope)

	def find_fn(name):
	    return self.pkg.root().find_with_imports([self.pkg.qualified_name(), ''], name)

	if v:
	    for impl in self.implements:
		implmod = find_fn(impl)
		print implmod
		scope = incut(scope, implmod, domain.ModDom([self]))

	    for dep, opts in self.depends:
		depmod = find_fn(dep)
		scope = incut(scope, depmod, domain.BoolDom([True]))
		for opt, d in opts.items():
		    scope = incut(scope, self.pkg[dep + '.' + opt], d)

	    if self.include_trigger:
		return trigger_handle(cont, scope, self.include_trigger, find_fn)
	else:
	    for impl in self.implements:
		implmod = find_fn(impl)
		scope = incut(scope, implmod, scope[implmod] - domain.ModDom([self]))

	return cont(scope)

    def fix_trigger(self, scope):
	for v in scope[self]:
	    try:
		return cut(scope, self, domain.BoolDom([v]))
	    except CutConflictException:
		pass
	raise CutConflictException(self)

    def implements(self):
	def get_impl(obj):
	    return [obj] + [get_impl(impl) for impl in obj.implements]

	return get_impl(self)[1:]	

    def is_list(self):
	return self.implements

    def __repr__(self):
	return "<Module %s, depends %s, sources %s>" % (self.name, self.depends, self.sources)

    def canon_repr(self):
	opts = map(lambda name_opt_pair: name_opt_pair[0], self.items())
	return common.repr.mod_canon(self.name, opts)

    def __hash__(self):
	return self.hash_value

