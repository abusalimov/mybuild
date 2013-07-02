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
from operator import attrgetter

from util.compat import *
from util import InstanceBoundTypeMixin


class Module(object):
    """A basic building block of Mybuild."""

    def __init__(self, func):
        self._init_func = func
        self._name = func.__name__

        class ModuleType(object):
            __slots__ = ()
            _module = self
            _module_name = self._name

        self._options = Optuple._new_type_options(ModuleType, func)

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
        return self._zipwith(self._fields, with_ellipsis, swap=True)

    def _zipwith(self, other, with_ellipsis=False, swap=False):
        it = zip(self, other) if not swap else zip(other, self)
        self_idx = int(bool(swap))
        return (it if with_ellipsis else
                (pair for pair in it if pair[self_idx] is not Ellipsis))

    def _mapwith(self, func):
        return self._make(map(func, self))

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
    def _options_from_func(cls, func):
        """Converts a function argspec into a list of Option objects."""

        args, va, kw, defaults = getargspec(func)
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

        head = [Option() for _ in xrange(len(option_args) - len(defaults))]
        tail = [option if isinstance(option, Option) else Option(option)
                for option in defaults]

        return [option.set(_name=name)
                for option, name in zip(head + tail, option_args)]

    @classmethod
    def _new_type_options(cls, module_type, func):
        options = cls._options_from_func(func)

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
        self.extendable = True

        self._values = set(values)
        if Ellipsis in self._values:
            raise ValueError('Ellipsis value is not permitted')

        self.set(**setup_flags)

    def set(self, **flags):
        if 'default' in flags:
            default = flags['default']
            if flags.pop('_check_default', False):
                if default not in self._values:
                    raise ValueError('default value (%r) not in values' %
                                     default)
            elif default is not Ellipsis:
                self._values.add(default)

        for attr in 'default', 'extendable', '_check_func', '_name', '_module':
            if attr in flags:
                setattr(self, attr, flags.pop(attr))

        if flags:
            raise TypeError('Unrecognized flag(s): %s' % ', '.join(flags))

        return self

    def _check(self, *values):
        if not self.extendable and set(values)-self._values:
            return False

        if all(map(getattr(self, '_check_func', lambda: True), values)):
            return False

        return True

    @classmethod
    def enum(cls, *values):
        return cls(*values, extendable=False)

    @classmethod
    def bool(cls, default=False):
        return cls(False, True, default=default,
                   extendable=False, _check_default=True)

    @classmethod
    def tristate(cls, default=None):
        return cls(None, False, True, default=default,
                   extendable=False, _check_default=True)

    @classmethod
    def str(cls, default=Ellipsis):
        return cls.of_type(str, default)

    @classmethod
    def of_type(cls, types, default=Ellipsis):
        ret = cls(_check_func=partial(isinstance, classinfo=types))

        if default is not Ellipsis:
            ret.set(default=default)

        return ret


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
    """
    Unrecoverable application errors indicating that something goes really
    wrong.
    """

