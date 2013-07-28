"""
Scoping and linking logic.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-26"


from .errors import *

from ...util import cached_property
from ...util import send_next_iter
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
        return '.'.join(frag for frag, loc in self.type_name_wlocs)

    @cached_property
    def type_root_wloc(self):
        """Resolved during linking a single my-file. May be a stub."""
        try:
            name_frags = self.type_name_wlocs
            name, loc = name_frags[0] if name_frags else (None, None)
            return self.scope[name], loc
        except KeyError:
            raise UnresolvedNameError(self, name, loc)

    @cached_property
    def type_object(self):
        """Resolved type object."""
        ret, loc = self.type_root_wloc

        for attr, attr_loc in self.type_name_wlocs[1:]:
            try:
                if isinstance(ret, Stub):
                    try:
                        ret = ret.named_children[attr]
                    except KeyError:
                        ret = Stub.to_object(ret, loc)
                    else:
                        continue
                ret = MyfileDeclarative.my_getattr_of(ret, attr)
            except AttributeError:
                raise UnresolvedAttributeError(self, ret, attr, attr_loc)
            finally:
                loc = attr_loc

        return Stub.to_object(ret, loc)

    @cached_property
    def type_args(self):
        return list(Stub.to_object(*arg_wloc) for arg_wloc in self.arg_wlocs)

    @cached_property
    def type_kwargs(self):
        return dict((kw, Stub.to_object(*arg_wloc))
                    for kw, arg_wloc in iteritems(self.kwarg_wlocs))

    @cached_property
    def resolved_object(self):
        """Called during global stubs linking.

        Safely resolves objects necessary to instantiate itself, and returns
        the resulting object.
        """
        linker = self.linker.global_linker
        reent_set = linker.reent_set

        if self in reent_set:
            raise ReferenceLoopChain(chain_init=self)

        reent_set.add(self)
        try:
            type_object = self.type_object
            type_args   = self.type_args
            type_kwargs = self.type_kwargs

        except ReferenceLoopChain as chain_exc:
            if chain_exc.chain_init is self:
                raise ReferenceLoopError(self, reversed(chain_exc.chain_wlocs))
            else:
                raise chain_exc(self)
        finally:
            reent_set.remove(self)

        try:
            ret = type_object(*type_args, **type_kwargs)

        except TypeError as e:
            raise InstantiationError(e, self)
        else:
            linker.objects.append((self, ret))
            return ret

    @classmethod
    def to_object(cls, obj, loc=None):
        if isinstance(obj, Stub):
            try:
                obj = obj.resolved_object
            except ReferenceLoopChain as chain_exc:
                chain_exc.attach_loc(loc)
                raise chain_exc
        return obj

    def __init__(self, linker, scope=None, parent=None):
        super(Stub, self).__init__()
        self.linker = linker
        self.scope = scope

        if parent is not None:
            if not parent.name:
                parent = parent.named_parent
            assert parent is None or parent.name
        self.named_parent = parent

        self.name = None

        self.type_name_wlocs = []  # parts of qualified name of a type

        self.arg_wlocs   = []  # positional type arguments: [(arg, loc)]
        self.kwarg_wlocs = {}  # keyword type arguments: {kw: (arg, loc)}

        self.attrs     = []
        self.docstring = None

    def init_header(self, type_name_wlocs, kwarg_pair_wlocs, name_wloc):
        self.type_name_wlocs = type_name_wlocs

        pair_it = send_next_iter(kwarg_pair_wlocs)

        # positional arguments
        for (kw, arg), loc in pair_it:
            if kw:
                pair_it.send(((kw, arg), loc))
                break
            self.arg_wlocs.append((arg, loc))

        # keyword arguments
        for (kw, arg), loc in pair_it:
            arg_wloc = (arg, loc)
            if not kw:
                raise ArgAfterKwargError(last_kwarg_wloc, arg_wloc)
            try:
                old_arg_wloc = self.kwarg_wlocs[kw]
            except KeyError:
                self.kwarg_wlocs[kw] = arg_wloc
            else:
                raise RepeatedKwargError(kw, old_arg_wloc, arg_wloc)
            last_kwarg_wloc = kw, arg_wloc

        name, _ = self.name_wloc = name_wloc
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
            args_str =   ', '.join(arg for arg, loc in self.arg_wlocs)
            kwargs_str = ', '.join('%s=%r' % (kw, arg)
                    for kw, (arg, loc) in iteritems(self.kwarg_wlocs))

            return '{type_name}{name}({type_args})'.format(
                type_name=self.type_name,
                name=name_str,
                type_args=', '.join(filter(None, (args_str, kwargs_str))))

        else:
            return '<object>'


# Scoping

class Scope(object):
    def raise_errors(self):
        pass
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
                old_value = self[name]
                del self[name]
            else:
                super(ConflictsAwareDictScope, self).__setitem__(name, value)
                return  # hot path

            self.conflicts[name] = [old_value]
        self.conflicts[name].append(value)

    def raise_errors(self):
        CompoundError.raise_if_any(
                MultipleDefinitionsError(name, values)
                   for name, values in iteritems(self.conflicts))


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
        return self.chain_wlocs[0][0]

    def __init__(self, chain_init):
        self.chain_wlocs = []
        self(chain_init)

    def __call__(self, chain_obj):
        self.chain_wlocs.append([chain_obj, None])
        return self

    def attach_loc(self, loc):
        self.chain_wlocs[-1][1] = loc

    def __str__(self):
        return ' -> '.join(map(str, reversed(self.chain_wlocs)))


# Linkage

class Linker(object):
    """docstring for Linker"""

    def __init__(self):
        super(Linker, self).__init__()
        self.stubs = list()


class GlobalLinker(Linker):

    def __init__(self):
        super(GlobalLinker, self).__init__()

        self.objects = list()  # topologically sorted
        self.reent_set = set()

    def link_global(self):

        def iter_errors():
            for stub in self.stubs:
                try:
                    stub.resolved_object  # populates self.objects
                except LinkageError as e:
                    yield e

        CompoundError.raise_if_any(iter_errors())

        assert len(self.objects) == len(self.stubs)



class LocalLinker(Linker):

    def __init__(self, global_linker):
        super(LocalLinker, self).__init__()
        self.global_linker = global_linker
        self.scopes = list()

    def link_local(self):

        def iter_errors():
            for stub in self.stubs:
                try:
                    stub.type_root_wloc
                except LinkageError as e:
                    yield e

            for scope in self.scopes:
                try:
                    scope.raise_errors()
                except LinkageError as e:
                    yield e


        CompoundError.raise_if_any(iter_errors())

        self.global_linker.stubs += self.stubs

