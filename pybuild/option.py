
import domain

from ops import *

class Option:
    def __init__(self, name, domain=None, pkg=None):
        self.name = name

        if not domain:
            domain = self.__class__.defdomain

        self.init_domain = domain

        self.domain = self.domain_class(domain)

        self.pkg = pkg

    def domain_class(self, domain, cls = None, *args, **kargs):
        if not cls:
            cls = self.__class__.domain_cls
        if isinstance(domain, tuple) or isinstance(domain, list):
            return cls(domain, *args, **kargs)
        else:
            return cls([domain], *args, **kargs)

    def cut_trigger(self, cont, scope, domain):
        return cont(scope)

    def add_trigger(self, scope):
        return scope

    def dom_key(self, dom_v):
        return 0

    def fix_trigger(self, scope, from_module = False):
        if not from_module:
            return scope

        try:
            dom = scope[self].release_it()
        except NotDefinedException, e:
            e.opt = self
            raise

        for v in sorted(dom, key = self.dom_key, reverse = True):
            try:
                return cut(scope, self, dom.__class__.single_value(v))
            except CutConflictException:
                pass
        raise CutConflictException(self, scope)

    def value(self, scope):
        dom = scope[self]
        try:
            value = dom.value()
        except OptException, excp:
            excp.opt = self
            raise

        return value

    def qualified_name(self):
        pkg_qual_name = self.pkg.qualified_name()
        if pkg_qual_name:
            return '%s.%s' % (pkg_qual_name, self.name)
        return self.name

    def build(self, ctx):
        pass

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.qualified_name())

    def copy(self):
        return self.__class__(self.name, self.init_domain, self.pkg)

class DefaultOption(Option):
    def __init__(self, name, domain=None, pkg=None, default=None):
        Option.__init__(self, name, domain, pkg)
        self.default = default 
        self.has_default = default != None

    def dom_key(self, dom_val):
        if dom_val == self.default:
            return 1
        return 0

    def add_trigger(self, scope):
        if self.has_default:
            scope[self] |= self.domain_class(self.default)
        return Option.add_trigger(self, scope) 

    def copy(self):  
        return self.__class__(self.name, self.init_domain, self.pkg, self.default)

class List(Option):
    defdomain = []
    domain_cls = domain.ListDom
    def build_repr(self):
        return None

class Integer(DefaultOption):
    defdomain = [domain.IntegerDom.wildcard]
    domain_cls = domain.IntegerDom
    def build_repr(self):
        return 'NUMBER'

class String(DefaultOption):
    defdomain = [domain.StringDom.wildcard]
    domain_cls = domain.StringDom
    def build_repr(self):
        return 'STRING'

class Boolean(DefaultOption):
    defdomain = [True, False]
    domain_cls = domain.BoolDom
    def build_repr(self):
        return 'BOOLEAN'

