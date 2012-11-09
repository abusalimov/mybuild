"""
Mybuild core types.

TODO docs. -- Eldar
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-09-15"

__all__ = [
    "Module",
    "Error",
    "InstanceError",
    "InternalError",
]


from collections import namedtuple
from functools import update_wrapper
from inspect import getargspec
from itertools import chain
from itertools import izip
from itertools import repeat
from operator import attrgetter

from expr import *


def module(fxn):
    return update_wrapper(Module(fxn), fxn)


class Module(object):
    """A basic building block of Mybuild."""

    class Type(object):
        """Base (marker) class for per-module types.

        Do not inherit or instantiate directly.
        """
        __slots__ = ()

        # These may be too strict checks, but it is OK,
        # since types are mapped to their modules one-to-one.
        _type_eq   = classmethod(lambda cls, other: cls is type(other))
        _type_hash = classmethod(id)

        def __eq__(self, other):
            return self._type_eq(type(other))
        def __hash__(self):
            return self._type_hash()

    _types = {} # attr-to-type

    @classmethod
    def register_type(cls, attr):
        """Deco maker for per-module classes."""

        if not isinstance(attr, basestring):
            raise TypeError("Attribure name must be a string, "
                            "got %s object instead: %r" % (type(attr), attr))

        if not attr.startswith('_'):
            raise ValueError("Attribure name must start with an underscore")

        def deco(target):
            if not isinstance(target, type):
                raise TypeError("'@%s.register_type(...)' must be applied "
                                "to a class, got %s object instead: %r" %
                                (cls.__name__, type(target), target))

            if not hasattr(target, '_new_type'):
                raise TypeError("'@%s.register_type(...)'-decorated class "
                                "must define a '_new_type' classmethod" %
                                (cls.__name__,))

            if hasattr(cls, attr) or attr in cls._types:
                raise ValueError("%s class already has attribure '%s'" %
                                 (cls.__name__, attr))

            cls._types[attr] = target

            return target

        return deco

    def __init__(self, fxn):
        super(Module, self).__init__()

        self._name = fxn.__name__
        module_type = type('Module_M%s' % (self._name,),
                           (self.Type,),
                           dict(__slots__=(),
                                _module=self,
                                _module_name=self._name))

        for attr, cls in self._types.iteritems():
            setattr(self, attr, cls._new_type(module_type, fxn))

    _options = property(attrgetter('_optuple_type._fields'))

    def __call__(self, **kwargs):
        return self._optuple_type._ellipsis._replace(**kwargs)

    def _to_optuple(self):
        return self._optuple_type._ellipsis

    def _to_expr(self):
        return self._atom

    def __repr__(self):
        return '%s(%s)' % (self._name, ', '.join(self._options))

@Module.register_type('_atom')
class ModuleAtom(Atom):
    """Module-bound atom."""
    __slots__ = ('_module',)

    def __init__(self, module):
        super(ModuleAtom, self).__init__()
        self._module = module

    def eval(self, fxn, *args, **kwargs):
        ret = fxn(self._module, *args, **kwargs)
        return self if ret is None else ret

    def __repr__(self):
        return '%s' % (self._module._name,)

    @classmethod
    def _new_type(cls, module_type, *args):
        return cls(module_type._module)


@Module.register_type('_optuple_type')
class Optuple(Module.Type):
    """Option tuple mixin type."""
    __slots__ = ()

    def _iter(self, with_ellipsis=False):
        return (iter(self) if with_ellipsis else
                (v for v in self if v is not Ellipsis))

    def _iterpairs(self, with_ellipsis=False):
        return self._izipwith(self._fields, with_ellipsis, swap=True)

    def _izipwith(self, other, with_ellipsis=False, swap=False):
        it = izip(self, other) if not swap else izip(other, self)
        self_idx = int(bool(swap))
        return (it if with_ellipsis else
                (pair for pair in it if pair[self_idx] is not Ellipsis))

    def _to_optuple(self):
        return self

    def __repr__(self):
        return '%s(%s)' % (self._module._name,
                           ', '.join('%s=%r' % pair
                                     for pair in self._iterpairs()))

    def __eq__(self, other):
        return self._type_eq(other) and tuple.__eq__(self, other)
    def __hash__(self):
        return self._type_hash() ^ tuple.__hash__(self)

    def _to_expr(self):
        option_atoms = tuple(A(v) for v,A in self._izipwith(self._atom_types))
        return (And._from_iterable(option_atoms) if option_atoms else
                self._module._to_expr())

    @classmethod
    def _options_defaults_from_fxn(cls, fxn):
        """Converts a function argspec into a (options, defaults) tuple."""

        args, va, kw, defaults = getargspec(fxn)
        defaults = defaults or ()

        if va is not None:
            raise TypeError(
                'Arbitrary arguments are not supported: *%r' % va)
        if kw is not None:
            raise TypeError(
                'Arbitrary keyword arguments are not supported: **%r' % kw)

        if not args:
            raise TypeError(
                'Module function must accept at least one argument')
        if len(args) == len(defaults):
            raise TypeError(
                'The first argument cannot have a default value: %r' % args[0])

        options = args[1:]
        for o in options:
            if not isinstance(o, basestring):
                raise TypeError(
                    'Tuple parameter unpacking is not supported: %r' % o)
            if o.startswith('_'):
                raise TypeError(
                    'Option name cannot start with an underscore: %r' % o)

        head_defaults = repeat((), len(options)-len(defaults))
        tail_defaults = ((v, not v) if isinstance(v, bool) else (v,)
            for v in defaults)
        defaults = tuple(chain(head_defaults, tail_defaults))

        return options, defaults

    @classmethod
    def _new_type(cls, module_type, fxn):
        options, defaults = cls._options_defaults_from_fxn(fxn)
        assert len(options) == len(defaults)

        optype_base = namedtuple('OptupleBase', options)

        bogus_attrs = set(a for a in dir(optype_base)
            if not a.startswith('_'))
        bogus_attrs.difference_update(options)

        for attr in bogus_attrs:
            setattr(optype_base, attr, property())

        new_type = type('Optuple_M%s' % (module_type._module_name,),
                        (cls, optype_base, module_type),
                        dict(__slots__=()))

        new_type._defaults = new_type._make(defaults)
        new_type._ellipsis = new_type._make(repeat(Ellipsis, len(options)))
        new_type._atom_types = \
            new_type._make(OptionAtom._new_type(module_type, o)
                           for o in options)

        optype_base._fields = new_type._make(options)

        return new_type

class OptionAtom(Module.Type, Atom):
    """A single bound option."""
    __slots__ = ('_value')

    value  = property(attrgetter('_value'))
    option = property(attrgetter('_option'))

    def __init__(self, value):
        super(OptionAtom, self).__init__()
        self._value = value

    def __eq__(self, other):
        return self._type_eq(other) and self._value == other._value
    def __hash__(self):
        return self._type_hash() ^ hash(self._value)

    def eval(self, fxn, *args, **kwargs):
        ret = fxn(self._module, option=self._option, value=self.value,
                *args, **kwargs)
        return self if ret is None else ret

    @classmethod
    def _replace(cls, new_value):
        return cls(new_value)

    @classmethod
    def _new_type(cls, module_type, option):
        return type('OptionAtom_M%s_O%s' % (module_type._module_name, option),
                    (cls, module_type),
                    dict(__slots__=(), _option=option))

    def __repr__(self):
        return '%s(%s=%r)' % (self._module._name, self._option, self._value)


class Error(Exception):
    """Base class for errors providing a logging-like constructor."""

    def __init__(self, msg, *args, **kwargs):
        if not isinstance(msg, basestring):
            raise TypeError("'msg' argument must be a string")
        if args and kwargs:
            raise TypeError('At most one of args or kwargs can be specified '
                            'at once, not both of them')

        super(Error, self).__init__(msg, args or kwargs or None)

    def __str__(self):
        msg, fmt_args = self.args
        return msg % fmt_args if fmt_args else msg

    def __repr__(self):
        msg, fmt_args = self.args
        type_name = type(self).__name__

        if not fmt_args:
            return '%s(%r)' % (type_name, msg)

        return '%s(%r, %s%r)' % (type_name, msg,
                                 '**' if isinstance(fmt_args, dict) else '*',
                                 fmt_args)

class InstanceError(Error):
    """
    Throwing this kind of errors from inside a module function indicates that
    instance is not viable anymore and thus shouldn't be considered.
    """

class InternalError(Exception):
    """Unrecoverable application errors indicating that goes really wrong."""

