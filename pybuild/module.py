
import re
import itertools

from exception import *

import option
import domain
import scope

from util import isvector

from ops  import *

from mybuild.common import repr as common_repr
from mybuild.build import inchdr

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

    dom_cls = dom.__class__

    if hasattr(opt, 'default') and opt.default in dom:
        dom = itertools.chain((opt.default,), dom)

    for value in dom:
        try:
            value_scope = cut(scope, opt, dom_cls.single_value(value))
            return trigger_handle(cont, value_scope, trig, *args, **kwargs)
        except CutConflictException or MultiValueException, excp:
            if excp.opt == opt:
                pass
            else:
                raise

    raise CutConflictException(opt)

class Entity():
    def find_fn(self, name):
        return self.pkg.root().find_with_imports([self.pkg.qualified_name(), ''], name)


class Module(Entity, option.Boolean, dict):
    def __init__(self, name, pkg=None, 
            static = False, mandatory = False,
            sources=[], options=[], super=None, 
            implements=(), depends=(), include_trigger=None):

        if mandatory:
            option.Boolean.__init__(self, name, default = True, pkg = pkg)
        else:
            option.Boolean.__init__(self, name, pkg = pkg)

        self.mandatory = mandatory
        self.static = static

        self.super_name = super
        self.super = None
        self.name = name
        self.include_trigger = include_trigger
        self.sources = sources

        self.options = []
        self.options += options
        self.hash_value = hash(self.qualified_name() + '.include_module')

        self.depends = []
        self.dependents = []

        for d in depends:
            if isvector(d):
                self.dependency_add(*d)
            else:
                self.dependency_add(d)

        self.implements = implements

        for o in self.options:
            o.pkg = self
            self[o.name] = o

    def dependency_add(self, modname, opts={}):
        self.depends.append((modname, opts))

    def dependent_add(self, depnt):
        self.dependents.append(depnt)

    def import_super(self, scope):
        if self.super_name and not self.super:
            self.super = self.find_fn(self.super_name)
            scope = self.super.import_super(scope)

            to_add = []
            for opt_name, opt in self.super.items():
                if not opt_name in self:
                    opt_copy = opt.copy()
                    self[opt_name] = opt_copy
                    to_add.append(opt_copy)

            return add_many(scope, to_add)
        return scope

    def add_trigger(self, scope):
        for impl in self.implements:
            implmod = self.pkg.root().find_with_imports([self.pkg.qualified_name(), ''], impl)
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

            for dep, opts in self.depends:
                depmod = self.find_fn(dep)
                scope = incut(scope, depmod, domain.BoolDom([True]))
                for opt, d in opts.items():
                    scope = incut(scope, self.pkg[dep + '.' + opt], d)

            if self.include_trigger:
                return trigger_handle(cont, scope, self.include_trigger, self.find_fn)
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

    def fix_trigger(self, scope):
        for iface in self.implements:
            scope = fix(scope, self.find_fn(iface))

        return option.Boolean.fix_trigger(self, scope)

    def is_list(self):
        return self.implements

    def __repr__(self):
        return "<Module %s, depends %s, sources %s>" % (self.name, self.depends, self.sources)

    def canon_repr(self):
        opts = map(lambda name_opt_pair: name_opt_pair[0], self.items())
        return common_repr.mod_canon(self.name, opts)

    def __hash__(self):
        return self.hash_value


    def build(self, ctx):
        if not self.value(ctx.model):
            return 

        srcs = []
        header_inc = []
        header_opts = []

        for src in self.sources:
            fsrc = src.build(ctx, self)
            if re.match('.*\.o', fsrc):
                srcs.append(fsrc)
            elif re.match('.*\.h', fsrc):
                header_inc.append(fsrc)

        for name, var in self.items():
            repr = var.build_repr()
            if not repr:
                continue
            header_opts.append(inchdr(repr, self.qualified_name(), name, ctx.model[var].value()))

        ctx.bld(features = 'module_header',
            name = self.qualified_name() + '_header',
            mod_name = self.qualified_name(),
            header_opts = header_opts,
            header_inc = header_inc)

        self.build_self(ctx, srcs)

    def build_self(self, ctx, srcs):
        tgt = self.qualified_name().replace('.', '_') 
        fts = 'c'

        if self.static:
            fts += ' cstlib'

        ctx.bld(
            features = fts, 
            target = tgt,
            #defines = ['__EMBUILD_MOD__'],
            includes = ctx.bld.env.includes,
            use = srcs,
        )

        ctx.bld.out.append(tgt)

