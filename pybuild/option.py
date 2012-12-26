
import domain

from ops import *

class Option:
    def __init__(self, name, domain=None, pkg=None):
        self.name = name

        if not domain:
            domain = self.__class__.defdomain

        self.raw_domain = domain

        self.domain = self.domain_class(domain)

        self.pkg = pkg

    def domain_class(self, domain, cls = None, *args, **kargs):
        if not cls:
            cls = self.__class__.domain_cls
        try:
            return cls(domain, *args, **kargs)
        except TypeError:
            return cls([domain], *args, **kargs)

    def cut_trigger(self, cont, scope, domain):
        return cont(scope)

    def add_trigger(self, scope):
        return scope

    def fix_trigger(self, scope):
        dom = scope[self]
        for v in dom:
            try:
                return cut(scope, self, dom.__class__.single_value(v))
            except CutConflictException:
                pass
        raise CutConflictException(self)

    def value(self, scope):
        dom = scope[self]
        try:
            value = dom.value()
        except Exception, excp:
            excp.opt = self
            raise

        return value

    def qualified_name(self):
        return '%s.%s' % (self.pkg.qualified_name(), self.name)

    def build(self, ctx):
        pass

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.qualified_name())

    def copy(self):
        return self.__class__(self.name, self.raw_domain, self.pkg)

class DefaultOption(Option):
    def __init__(self, name, domain=None, pkg=None, default=None):
        Option.__init__(self, name, domain, pkg)
        self.default = default 

    def fix_trigger(self, scope):
        dom = scope[self]
        if hasattr(self, 'default') and self.default in dom:
            scope = cut(scope, self, domain.Domain([self.default]))
        else:
            return Option.fix_trigger(self, scope)

        return scope

    def copy(self):  
        return self.__class__(self.name, self.raw_domain, self.pkg, self.default)

class List(Option):
    defdomain = []
    domain_cls = domain.ListDom
    def build_repr(self):
        return None

class Integer(DefaultOption):
    defdomain = range(0, 0x20000)
    domain_cls = domain.IntegerDom
    def build_repr(self):
        return 'NUMBER'

class String(DefaultOption):
    def build_repr(self):
        return 'STRING'

class Boolean(DefaultOption):
    defdomain = [True, False]
    domain_cls = domain.BoolDom
    def build_repr(self):
        return 'BOOLEAN'

