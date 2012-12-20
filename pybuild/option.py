
import domain

from ops import *

class Option:
    def __init__(self, name, domain=None, pkg=None):
        self.name = name

        if not domain:
            domain = self.__class__.defdomain

        self.domain = self.__class__.domain_class(domain)

        self.pkg = pkg

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

class List(Option):
    defdomain = []
    domain_class = domain.ListDom
    def build_repr(self):
        return None

class Integer(DefaultOption):
    defdomain = range(0, 0x10000)
    domain_class = domain.IntegerDom
    def build_repr(self):
        return 'NUMBER'

class String(DefaultOption):
    def build_repr(self):
        return 'STRING'

class Boolean(DefaultOption):
    defdomain = [True, False]
    domain_class = domain.BoolDom
    def build_repr(self):
        return 'BOOLEAN'

