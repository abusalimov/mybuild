
import itertools

from exception import *

import option
import domain
import scope

from util import isvector

from ops  import *

from mybuild.common.module import ModuleBuildOps

import logging, warnings

def trigger_handle(cont, scope, self, *args, **kwargs):
    opt = None
    try:
        trig_ret = self.include_trigger(scope, *args, **kwargs)

        if isinstance(trig_ret, Scope):
            return cont(trig_ret)

        return cont(scope)
    except MultiValueException, excp:
        opt = excp.opt
        warnings.warn("%s is accessed from %s' user code, but it haven't fully specified, iterating withih %s" % \
                (opt, self.qualified_name(), scope[opt]))

    dom = scope[opt]

    dom_cls = dom.__class__

    if hasattr(opt, 'default') and opt.default in dom:
        dom = itertools.chain((opt.default,), dom)

    for value in dom:
        try:
            value_scope = cut(scope, opt, dom_cls.single_value(value))
            return trigger_handle(cont, value_scope, self, *args, **kwargs)
        except CutConflictException or MultiValueException, excp:
            pass

    raise CutConflictException(opt, scope)

class Entity():
    def find_fn(self, name):
        try:
            return self.pkg.root().find_with_imports([self.pkg.qualified_name(), ''], name)
        except AttributeError, excp:
            raise AttributeError(
                    "Can't find '%s', referenced from %s" % 
                    (excp.message, self))
            

class Module(ModuleBuildOps, Entity, option.Boolean):
    def __init__(self, name, pkg=None, 
            static = False, mandatory = False,
            sources=[], options=[], super=None, 
            implements=(), depends=(), include_trigger=None):

        if mandatory:
            option.Boolean.__init__(self, name, domain = [True], pkg = pkg)
        else:
            option.Boolean.__init__(self, name, pkg = pkg)

        self.mandatory = mandatory
        self.static = static

        self.super_name = super
        self.super = None
        self.name = name
        self.include_trigger = include_trigger
        self.sources = sources

        self.hash_value = hash(self.qualified_name() + '.include_module')

        self.depends = []
        self.dependents = []

        for d in depends:
            if isvector(d):
                self.dependency_add(*d)
            else:
                self.dependency_add(d)

        self.implements = implements
    
        self.opt_dict = {}

        for o in options:
            if hasattr(self, o.name):
                raise Exception(
                    "Sorry, can't have option with name '%s' in %s"
                    %(o.name, self))
            o.pkg = self
            self.opt_dict[o.name] = o

    def contents(self):
        return self.opt_dict.items()

    def items(self):
        raise Exception()

    def __getattr__(self, attr):
        try:
            return self.opt_dict[attr]
        except KeyError:
            raise AttributeError(attr)

    def dependency_add(self, modname, opts={}):
        self.depends.append((modname, opts))

    def dependent_add(self, depnt):
        self.dependents.append(depnt)

    def import_super(self, scope):
        if self.super_name and not self.super:
            self.super = self.find_fn(self.super_name)
            scope = self.super.import_super(scope)

            to_add = []
            for opt_name, opt in self.super.opt_dict.items():
                if not opt_name in self.opt_dict:
                    opt_copy = opt.copy()
                    opt_copy.pkg = self
                    self.opt_dict[opt_name] = opt_copy
                    to_add.append(opt_copy)

            return add_many(scope, to_add)
        return scope

    def add_trigger(self, scope):
        for impl in self.implements:
            implmod = self.find_fn(impl)
            scope[implmod] |= domain.ModDom([self])

        for (dep_name, dep_opts) in self.depends:
            self.find_fn(dep_name).dependent_add(self)

        return self.import_super(scope)

    def cut_trigger(self, cont, scope, old_domain):
        dom = scope[self]
        if len(dom) > 1: 
            return cont(scope)
        v = dom.value()

        if v:
            for impl in self.implements:
                implmod = self.find_fn(impl)
                scope = incut(scope, implmod, domain.ModDom([self]))

            dep_cut = []
            
            for dep, opts in self.depends:
                dep_cut += [(dep, True)] + [(dep + '.' + opt_name, val) for opt_name, val in opts.items()]

            scope = cut_many_fancy(scope, self.find_fn, dep_cut)

            if self.include_trigger:
                return trigger_handle(cont, scope, self, self.find_fn)
        else:
            for impl in self.implements:
                implmod = self.find_fn(impl)
                scope = incut(scope, implmod, scope[implmod] - domain.ModDom([self]))

            for dependent in self.dependents:
                scope = incut(scope, dependent, domain.BoolDom([False]))

        return cont(scope)

    def implements(self):
        def get_impl(obj):
            return [obj] + [get_impl(impl) for impl in obj.implements]

        return get_impl(self)[1:]       

    def fix_trigger(self, scope, from_module = False):
        for iface in self.implements:
            scope = fix(scope, self.find_fn(iface), from_module = True)

        scope = option.Boolean.fix_trigger(self, scope, from_module = True) 

        if self.value(scope):
            for o in self.opt_dict.values():
                scope = fix(scope, o, from_module = True)

        return scope
        

    def is_list(self):
        return self.implements

    def __repr__(self):
        return "<Module %s>" % (self.qualified_name())

    def canon_repr(self):
        opts = map(lambda name_opt_pair: name_opt_pair[0], self.items())
        return common_repr.mod_canon(self.name, opts)

    def __hash__(self):
        return self.hash_value

    def isbuilding(self, model):
        return self.value(model)

    def get_sources(self):
        return self.sources

    def get_depends(self):
        return [self.find_fn(d) for d, opt in self.depends]

    def get_options(self):
        return self.opt_dict.values()

    def islib(self):
        return self.static

    def isinterface(self):
        return False
