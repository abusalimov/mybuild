
from exception import *

from ops       import cut, incut

from module import Module
from option import DefaultOption
from domain import BoolDom, ModDom
from scope  import BaseScope

class DefImplMod(Module):
    def add_trigger(self, scope):
        return scope

    def cut_trigger(self, cont, scope, old_domain):
        domain = scope[self]

        if domain.value():
            raise CutConflictException(self)

        return cont(scope)

class Interface(DefaultOption, BaseScope):
    def __init__(self, name, pkg, default=None, super=None):
        self.name = name
        self.hash_value = hash(name + ".include_interface")
        self.pkg = pkg
        self.parent = super

        if default:
            self.default_name = default

        self.def_impl = DefImplMod(self.qualified_name() + "_def_impl", pkg=pkg, implements=[self.name])
        self.domain = ModDom([self.def_impl])

    def items(self):
        return [('Default Impl', self.def_impl)]

    def add_trigger(self, scope):
        def_name = getattr(self, 'default_name', None)

        if def_name:
            self.default = self.pkg.root().find_with_imports([self.pkg.qualified_name(), ''], def_name)

        return scope


    def cut_trigger(self, cont, scope, old_domain):
        domain = scope[self]
        cant_be = old_domain - domain
        for old_impl in cant_be:
            scope = cont(incut(scope, old_impl, BoolDom([False])))

        if len(domain) == 1:
            return cont(incut(scope, domain.value(), BoolDom([True])))

        return cont(scope)

    def __repr__(self):
        return "Interface '" + self.name + "'"

    def __hash__(self):
        return self.hash_value

    
    def build(self, ctx): 
        header_inc = []

        def mod_hdr_fn(mod):
            return 'module/%s.h' % (mod.qualified_name().replace('.','/'),)

        #XXX
        for impl in ctx.model[self]:
            header_inc.append(mod_hdr_fn(impl)) 

        ctx.bld(features = 'module_header',
            name = self.qualified_name() + '_header',
            mod_name = self.qualified_name(),
            header_opts = [],
            header_inc = header_inc)
        

