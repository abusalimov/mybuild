
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
    def __init__(self, name, pkg, super=None):
        self.name = name
        self.hash_value = hash(name + ".include_interface")
        self.pkg = pkg
        self.parent = super
        self.def_impl = DefImplMod(self.qualified_name() + "_def_impl", pkg=pkg, implements=[self])
        self.domain = ModDom([self.def_impl])

    def items(self):
        return [('Default Impl', self.def_impl)]

    def cut_trigger(self, cont, scope, old_domain):
        domain = scope[self]
        cant_be = old_domain - domain
        for old_impl in cant_be:
            scope = cont(incut(scope, old_impl, BoolDom([False])))

        if len(domain) == 1:
            return cont(incut(scope, domain.value(), BoolDom([True])))

        return cont(scope)

    def fix_trigger(self, scope):
        for impl in scope[self]:
            try:
                return cut(scope, self, ModDom([impl]))
            except CutConflictException:
                pass
        
        raise CutConflictException(self)

    def __repr__(self):
        return "Interface '" + self.name + "'"

    def __hash__(self):
        return self.hash_value

    
    def build(self, bld, scope): 
        header_inc = []

        for impl in scope[self]:
            header_inc.append('module/%s.h' % (impl.qualified_name().replace('.','/'),)) #XXX

        bld(features = 'module_header',
            mod_name = self.qualified_name(),
            header_opts = [],
            header_inc = header_inc)

