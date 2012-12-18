"""
Mybuild core types.

TODO docs. -- Eldar
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-09-15"

__all__ = [
    "Module",
    "Option",
    "Optuple",
    "Error",
    "InstanceError",
    "InternalError",
]


from collections import namedtuple
from inspect import getargspec
from itertools import chain
from itertools import izip
from itertools import repeat
from operator import attrgetter

import pdag
from util import DynamicAttrsMixin
from util import InstanceBoundTypeMixin


class Module(DynamicAttrsMixin):
    """A basic building block of Mybuild."""

    class Type(InstanceBoundTypeMixin):
        pass

    def __init__(self, fxn):
        self._name = fxn.__name__
        module_type = type('Module_M%s' % (self._name,),
                           (self.Type,),
                           dict(__slots__=(),
                                _module=self,
                                _module_name=self._name))

        self._init_attrs(module_type, fxn)

    def __call__(self, **kwargs):
        return self._options._ellipsis._replace(**kwargs)

    def _to_optuple(self):
        return self._options._ellipsis

    def _to_pnode(self):
        return self._atom

    def __repr__(self):
        return '%s(%s)' % (self._name, ', '.join(self._options._fields))

@Module.register_attr('_atom_type')
class ModuleAtom(pdag.Atom):
    __slots__ = ()

    def __str__(self):
        return self._module_name

    @classmethod
    def _new_type(cls, module_type, *ignored):
        return type('ModuleAtom_M%s' % (module_type._module_name,),
                    (cls, module_type),
                    dict(__slots__=()))


@Module.register_attr('_options')
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

    def _to_pnode(self):
        atoms = tuple(o._atom(v) for v,o in self._izipwith(self._options))
        return (expr.And._from_iterable(atoms) if atoms else
                self._module._to_pnode())

    @classmethod
    def _options_from_fxn(cls, fxn):
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

        option_args = args[1:]
        for a in option_args:
            if not isinstance(a, basestring):
                raise TypeError(
                    'Tuple parameter unpacking is not supported: %r' % a)
            if a.startswith('_'):
                raise TypeError(
                    'Option name cannot start with an underscore: %r' % a)

        head = (Option() for _ in xrange(len(defaults), len(option_args)))
        tail = (o if isinstance(o, Option) else Option(o) for o in defaults)

        return tuple(o.set(_name=a)
                     for o,a in izip(chain(head, tail), option_args))

    @classmethod
    def _new_type(cls, module_type, fxn):
        options = cls._options_from_fxn(fxn)

        optuple_base = namedtuple('OptupleBase', (o._name for o in options))

        bogus_attrs = set(a for a in dir(optuple_base)
                          if not a.startswith('_'))
        bogus_attrs.difference_update(optuple_base._fields)
        for attr in bogus_attrs:
            setattr(optuple_base, attr, property())

        new_type = type('Optuple_M%s' % (module_type._module_name,),
                        (cls, optuple_base, module_type),
                        dict(__slots__=()))

        optuple_base._fields = new_type._make(optuple_base._fields)
        new_type._ellipsis = new_type._make(repeat(Ellipsis, len(options)))
        new_type._options = new_type._make(o.set(_module=module_type._module)
                                            ._init_types(module_type)
                                           for o in options)

        return new_type._options


class Option(DynamicAttrsMixin):

    class Type(Module.Type):
        pass

    def __init__(self, *values, **setup_flags):
        super(Option, self).__init__()

        self._default = values[0] if values else Ellipsis
        self._allow_others = True

        self._values = frozenset(values)
        if Ellipsis in self._values:
            raise ValueError('Ellipsis value is not permitted')

        self.set(**setup_flags)

    def _init_types(self, module_type):
        option_type = type('Option_M%s_O%s' % (module_type._module_name,
                                               self._name),
                           (self.Type, module_type),
                           dict(__slots__=(),
                                _option=self,
                                _option_name=self._name))
        self._init_attrs(option_type)
        return self

    def set(self, **flags):
        if 'default' in flags:
            default = flags.pop('default')
            self._default = default
            if default is not Ellipsis and default not in self._values:
                self._values |= {default}

        for attr in 'allow_others', '_name', '_module':
            if attr in flags:
                setattr(self, attr, flags.pop(attr))

        if flags:
            raise TypeError('Unrecognized flags: %s' % ', '.join(flags.keys()))

        return self

    @classmethod
    def enum(cls, *values):
        return cls(*values, allow_others=False)

    @classmethod
    def bool(cls, default=False):
        return cls(True, False, default=default, allow_others=False)

@Option.register_attr('_atom_type')
class OptionValueAtom(pdag.Atom):
    __slots__ = '_value'

    def __init__(self, value):
        super(OptionValueAtom, self).__init__()
        self._value = value

    def __str__(self):
        return '(%s.%s==%s)' % (self._module_name,
                                self._option_name, self._value)

    @classmethod
    def _new_type(cls, option_type):
        return type('OptionAtom_M%s_O%s' % (option_type._module_name,
                                            option_type._option_name),
                    (cls, option_type),
                    dict(__slots__=()))


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

