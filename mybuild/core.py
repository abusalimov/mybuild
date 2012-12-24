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
    "InternalError",
]


from collections import namedtuple
from inspect import getargspec
from itertools import izip
from operator import attrgetter

from util import InstanceBoundTypeMixin


class Module(object):
    """A basic building block of Mybuild."""

    def __init__(self, fxn):
        self._init_fxn = fxn
        self._name = fxn.__name__

        class ModuleType(object):
            __slots__ = ()
            _module = self
            _module_name = self._name

        self._options = Optuple._new_type_options(ModuleType, fxn)

    def __call__(self, **kwargs):
        return self._options._ellipsis._replace(**kwargs)

    def _to_optuple(self):
        return self._options._ellipsis

    def __repr__(self):
        return '%s(%r)' % (self._name, ', '.join(self._options._fields))


class Optuple(InstanceBoundTypeMixin):
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

    @classmethod
    def _options_from_fxn(cls, fxn):
        """Converts a function argspec into a list of Option objects."""

        args, va, kw, defaults = getargspec(fxn)
        defaults = defaults or ()

        if va is not None:
            raise TypeError(
                'Arbitrary arguments are not supported: *%s' % va)
        if kw is not None:
            raise TypeError(
                'Arbitrary keyword arguments are not supported: **%s' % kw)

        if not args:
            raise TypeError(
                'Module function must accept at least one argument')
        if len(args) == len(defaults):
            raise TypeError(
                'The first argument cannot have a default value: %s' % args[0])

        option_args = args[1:]
        for arg in option_args:
            if not isinstance(arg, basestring):
                raise TypeError(
                    'Tuple parameter unpacking is not supported: %s' % arg)
            if arg.startswith('_'):
                raise TypeError(
                    'Option name cannot start with an underscore: %s' % arg)

        head = [Option() for _ in xrange(len(defaults), len(option_args))]
        tail = [option if isinstance(option, Option) else Option(option)
                for option in defaults]

        return map(lambda option, name: option.set(_name=name),
                   head + tail, option_args)

    @classmethod
    def _new_type_options(cls, module_type, fxn):
        options = cls._options_from_fxn(fxn)

        optuple_base = namedtuple('OptupleBase',
                                  (option._name for option in options))

        bogus_attrs = set(a for a in dir(optuple_base)
                          if not a.startswith('_'))
        bogus_attrs.difference_update(optuple_base._fields)
        for attr in bogus_attrs:
            setattr(optuple_base, attr, property())

        new_type = type('Optuple_M%s' % module_type._module_name,
                        (cls, optuple_base, module_type),
                        dict(__slots__=()))

        optuple_base._fields = new_type._make(optuple_base._fields)
        new_type._ellipsis = new_type._make(Ellipsis for _ in options)
        new_type._options = new_type._make(
            option.set(_module=module_type._module) for option in options)

        return new_type._options


class Option(object):

    def __init__(self, *values, **setup_flags):
        super(Option, self).__init__()

        self.default = values[0] if values else Ellipsis
        self.allow_others = True

        self._values = set(values)
        if Ellipsis in self._values:
            raise ValueError('Ellipsis value is not permitted')

        self.set(**setup_flags)

    def set(self, **flags):
        if 'default' in flags:
            default = flags.pop('default')
            self.default = default
            if default is not Ellipsis and default not in self._values:
                self._values.add(default)

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

class InternalError(Exception):
    """Unrecoverable application errors indicating that goes really wrong."""

