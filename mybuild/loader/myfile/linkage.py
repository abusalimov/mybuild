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

    @classmethod
    def my_getattr_of(cls, obj, attr):
        if isinstance(obj, cls):
            obj.my_getattr(attr)
        else:
            cls.my_getattr(obj, attr)


class Stub(object):
    """docstring for Stub"""

    def __init__(self, name=None):
        super(Stub, self).__init__()
        self.name    = name

        self.resolve_hooks = []  # updated upon resolving links to this object

    def resolve_to(self, payload):
        self.resolve_hooks = [hook for hook in self.resolve_hooks
                              if hook(payload)]


class ObjectStub(Stub, MyfileDeclarative):
    """docstring for ObjectStub"""

    @cached_property
    def type_root(self):
        """Resolved during linking a single my-file."""
        try:
            return self.scope[self.type_name]
        except KeyError:
            raise UnresolvedNameError("name '%s' is not resolved" %
                                           self.type_name)

    @cached_property
    def type_or_stub(self):
        """Called during global stubs linking.

        Some attributes may still remain unresolved.
        """
        ret = self.type_root

        nr_got = 0
        try:
            for nr_got, attr in enumerate(self.type_attrs):
                ret = MyfileDeclarative.my_getattr_of(ret, attr)

        except AttributeError as e:
            if not isinstance(ret, Stub):
                raise
        finally:
            del self.type_attrs[:nr_got]

        if isinstance(ret, Stub):
            def resolve(obj):
                self.type_or_stub = obj
            ret.resolve_hooks.append(resolve)

        return ret  # bypass AttributeError (if any)

    @cached_property
    def type_object(self):
        """Resolved during final objects resolution."""

        ret = self.type_or_stub

        if isinstance(ret, Stub):
            ret = ret.as_object

        if self.type_attrs:
            raise UnresolvedAttributeError()

        return ret

    @cached_property
    def as_object(self):
        ret = self.type_or_stub

        if isinstance(ret, Stub):
            pass


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

class BuiltinScope(DelegatingScope):
    def __missing__(self, key):
        if key is None:
            return dict  # for objects with no type info ({})
        return super(BuiltinScope, self).__missing__(key)


class LinkageError(Exception):
    pass

class CompoundError(LinkageError):
    def __init__(self, *causes):
        super(CompoundError, self).__init__('\n'.join(map(str, causes)))

class UnresolvedNameError(LinkageError, NameError):
    pass

class UnresolvedAttributeError(LinkageError, AttributeError):
    pass


class Linker(object):
    """docstring for Linker"""

    def __init__(self):
        super(Linker, self).__init__()
        self.all_objects = list()

class GlobalLinker(object):
    pass


class LocalLinker(Linker):

    def __init__(self, global_linker):
        super(LocalLinker, self).__init__()
        self.global_linker = global_linker
        self.all_scopes = list()

    def link_local(self):

        def has_unresolved_type(obj):
            try:
                obj.type_root
            except UnresolvedNameError as e:
                return e

        unresolved_errors = list(filter(has_unresolved_type, self.all_objects))
        if unresolved_errors:
            raise CompoundError(*unresolved_errors)

        self.global_linker.all_objects += self.all_objects

