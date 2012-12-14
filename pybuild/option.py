
import domain

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
	scope[self] = domain.Domain([dom.force_value()])

	return scope

    def qualified_name(self):
	return '%s.%s' % (self.pkg.qualified_name(), self.name)

class DefaultOption(Option):
    def __init__(self, name, domain=None, pkg=None, default=None):
	Option.__init__(self, name, domain, pkg)
	self.default = default 

    def fix_trigger(self, scope):
	dom = scope[self]
	if hasattr(self, 'default') and self.default in dom:
	    scope[self] = domain.Domain([self.default])
	else:
	    return Option.fix_trigger(self, scope)

	return scope

class List(Option):
    defdomain = []
    domain_class = domain.ListDom
    
class Integer(DefaultOption):
    defdomain = range(0, 0x10000)
    domain_class = domain.IntegerDom

class String(DefaultOption):
    pass

class Boolean(DefaultOption):
    defdomain = [True, False]
    domain_class = domain.BoolDom

