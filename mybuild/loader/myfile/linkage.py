"""
Scoping and linking logic.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-26"


from .errors import *

from ...util import cached_property

from ...util.compat import *


class MyfileDeclarative(object):
    """docstring for MyfileDeclarative"""

    def my_getattr(self, attr):
        return getattr(self, attr)

    @classmethod
    def my_getattr_of(cls, obj, attr):
        if isinstance(obj, cls):
            return obj.my_getattr(attr)
        else:
            return getattr(obj, attr)


class Stub(object):
    """docstring for Stub"""

    @property
    def type_name(self):
        return '.'.join(self.type_name_frags)

    @cached_property
    def type_root(self):
        """Resolved during linking a single my-file. May be a stub."""
        try:
            return self.scope[self.type_name_frags and self.type_name_frags[0]]
        except KeyError:
            raise UnresolvedNameError("name '%s' is not resolved" %
                                      self.type_name)

    @cached_property
    def type_object(self):
        """Resolved type object."""
        ret = self.type_root

        for attr in self.type_name_frags[1:]:
            if isinstance(ret, Stub):
                try:
                    ret = ret.named_children[attr]
                except KeyError:
                    ret = Stub.to_object(ret)
                else:
                    continue

            ret = MyfileDeclarative.my_getattr_of(ret, attr)

        return Stub.to_object(ret)

    @cached_property
    def type_args(self):
        return list(map(Stub.to_object, self.args))

    @cached_property
    def type_kwargs(self):
        return dict((kw, Stub.to_object(arg))
                    for kw, arg in iteritems(self.kwargs))

    @cached_property
    def as_object(self):
        """Called during global stubs linking.

        Safely resolves objects necessary to instantiate itself, and returns
        the resulting object.
        """
        try:
            self.__reent_guard
        except AttributeError:
            self.__reent_guard = None
        else:
            raise ReferenceLoopChain(chain_init=self)

        try:
            return self.type_object(*self.type_args, **self.type_kwargs)

        except ReferenceLoopChain as chain_ex:
            if chain_ex.chain_init is self:
                raise ReferenceLoopError(chain_ex)
            else:
                raise chain_ex(self)

        finally:
            del self.__reent_guard

    @classmethod
    def to_object(cls, obj):
        if isinstance(obj, Stub):
            obj = obj.as_object
        return obj

    def __init__(self, scope=None, parent=None):
        super(Stub, self).__init__()
        self.scope = scope

        if parent is not None:
            if not parent.name:
                parent = parent.named_parent
            assert parent.name
        self.named_parent = parent

        self.name = None

        self.type_name_frags = []  # parts of qualified name of a type

        self.args   = []  # positional type arguments TODO unused
        self.kwargs = {}  # keyword type arguments

        self.attrs     = []
        self.docstring = None

    def init_header(self, type_name, kwargs, name=None):
        if type_name:
            self.type_name_frags = type_name.split('.')

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

    def __repr__(self):
        name_str = self.name.join('  ') if self.name else ''

        if self.type_name:
            args_str =   ', '.join(self.args)
            kwargs_str = ', '.join('%s=%r' % kwarg
                                   for kwarg in iteritems(self.kwargs))

            return '{type_name}{name}({type_args})'.format(
                type_name=self.type_name,
                name=name_str,
                type_args=', '.join(filter(None, (args_str, kwargs_str))))

        else:
            return '<object>'


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
    def __getitem__(self, key):
        if key is None:
            return dict  # for objects with no type info ({})
        return super(BuiltinScope, self).__missing__(key)


class ReferenceLoopChain(Exception):
    @property
    def chain_init(self):
        return self.chain[0]

    def __init__(self, chain_init):
        self.chain = [chain_init]

    def __call__(self, chain_obj):
        self.chain.append(chain_obj)
        return self

    def __str__(self):
        return ' -> '.join(map(str, reversed(self.chain)))


class Linker(object):
    """docstring for Linker"""

    def __init__(self):
        super(Linker, self).__init__()
        self.all_objects = list()

    def _raise_compound_if_any(self, errors):
        if errors:
            raise CompoundError(*errors)


class GlobalLinker(Linker):

    def link_global(self):

        def iter_any_errors():
            for obj in self.all_objects:
                try:
                    obj.as_object
                except LinkageError as e:
                    yield e

        self._raise_compound_if_any(tuple(iter_any_errors()))



class LocalLinker(Linker):

    def __init__(self, global_linker):
        super(LocalLinker, self).__init__()
        self.global_linker = global_linker
        self.all_scopes = list()

    def link_local(self):

        def iter_type_root_errors():
            for obj in self.all_objects:
                try:
                    obj.type_root
                except UnresolvedNameError as e:
                    yield e

        self._raise_compound_if_any(tuple(iter_type_root_errors()))

        self.global_linker.all_objects += self.all_objects

