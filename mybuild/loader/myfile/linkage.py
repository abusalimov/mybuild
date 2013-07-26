"""
Scoping and linking logic.
"""

__author__ = "Eldar Abusalimov"


from ...util import cached_property

from ...util.compat import *


class MyfileDeclarative(object):
    """docstring for MyfileDeclarative"""

    def my_getattr(self, attr):
        return getattr(self, attr)


class Stub(object):
    """docstring for Stub"""

    def __init__(self, name=None):
        super(Stub, self).__init__()
        self.name    = name

        self.resolve_hooks = []  # updated upon resolving links to this object

    def resolve_to(self, payload):
        for hook in self.resolve_hooks:
            hook(payload)


class ObjectStub(Stub, MyfileDeclarative):
    """docstring for ObjectStub"""

    @cached_property
    def type_root(self):
        try:
            return self.scope[self.type_name]
        except KeyError:
            raise UnresolvedReferenceError("name '%s' is not defined" %
                                           self.type_name)

    @cached_property
    def type_or_stub(self):
        """Reference to a resolved type (ObjectStub)."""
        ret = self.type_root

        try:
            for attr in self.type_attrs:
                if isinstance(ret, MyfileDeclarative):
                    ret = ret.my_getattr(attr)
                else:
                    ret = getattr(ret, attr)

        except AttributeError as e:
            raise UnresolvedAttributeError(*e.args)

        if isinstance(ret, Stub):
            def resolve(payload):
                self.type_or_stub = payload
            ret.resolve_hooks.append(resolve)

        return ret

    def __init__(self, scope=None, parent=None):
        super(ObjectStub, self).__init__()
        self.scope = scope

        if parent is not None:
            if not parent.name:
                parent = parent.named_parent
            assert parent.name
        self.named_parent = parent

        self.type_name = None  # qualified name of a type

        self.args   = []  # positional type arguments TODO unused
        self.kwargs = {}  # keyword type arguments

        self.attrs     = []
        self.docstring = None

    def init_header(self, type_name, kwargs, name=None):
        name_frags = type_name.split('.') if type_name else [None]
        self.type_name  = name_frags[0]
        self.type_attrs = name_frags[1:]

        self.kwargs = kwargs
        self.name   = name

        if name:
            self.named_children = {}
            self.scope[name] = self
            parent = self.named_parent
            if parent is not None:
                parent.named_children[name] = self

    def init_body(self, attrs, docstring):
        self.attrs     = attrs
        self.docstring = docstring

    def my_getattr(self, attr):
        try:
            return self.named_children[attr]
        except KeyError:
            raise AttributeError  # TODO think about it

    def __repr__(self):
        return '{type_name} in ({scope}) {name}({kwargs}){attrs}'.format(
                    type_name='.'.join([self.type_name] + self.type_attrs)
                        if self.type_name else '',
                    scope=self.scope,
                    name=self.name or '',
                    kwargs=dict(self.kwargs) or '',
                    attrs=dict(self.attrs) or '')


class Scope(object):
    def __getitem__(self, name):
        raise KeyError
    def __repr__(self):
        return type(self).__name__.join('<>')

class MutableScope(Scope):
    def __setitem__(self, name, value):
        pass


class DelegatingScope(Scope):
    """docstring for DelegatingScope"""

    def __init__(self, parent=Scope()):
        super(DelegatingScope, self).__init__()
        self.parent = parent

    def __missing__(self, key):
        return self.parent[key]

    def __repr__(self):
        return '%s -> %r' % (super(DelegatingScope, self).__repr__(),
                             self.parent)


class DictScope(dict, MutableScope):
    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, list(self))


class ConflictsAwareDictScope(DictScope):
    """Stores conflicting items detected upon setting a value for an existing
    name."""

    def __init__(self):
        super(ConflictsAwareDictScope, self).__init__()
        self.conflicts = dict()    # {name: [values]}

    def __setitem__(self, name, value):
        if name not in self.conflicts:
            if name in self:
                del self[name]
            else:
                super(ConflictsAwareDictScope, self).__setitem__(name, value)
                return  # hot path

            self.conflicts[name] = [old_value]
        self.conflicts[name].append(value)


class ObjectScope(DelegatingScope, ConflictsAwareDictScope):
    pass


class LinkageError(Exception):
    pass

class UnresolvedReferenceError(LinkageError, NameError):
    pass

class UnresolvedAttributeError(LinkageError, AttributeError):
    pass


