"""
Mybuild core types.

TODO docs. -- Eldar
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-09-15"

__all__ = [
    "ModuleType",
    "Module",
    "Option",
    "Optuple",
    "MybuildError",
]


from collections import namedtuple
from functools import partial
from inspect import getargspec
from operator import attrgetter
import sys

from util import getter
from util import invoker
from util import InstanceBoundTypeMixin

from util.compat import *


class ModuleType(type):
    """Metaclass of Mybuild modules."""

    def __new__(mcls, name, bases, attrs, **kwargs):
        """Suppresses any keyword arguments."""
        return super(ModuleType, mcls).__new__(mcls, name, bases, attrs)

    def __init__(cls, name, bases, attrs, options=None):
        """
        Subclasses must provide an 'options' argument, otherwise a class is
        considered intermediate and behaves as a regular Python metaclass.
        """
        super(ModuleType, cls).__init__(name, bases, attrs)

        cls._fullname = cls._name = cls.__name__
        try:
            pymodule = sys.modules[cls.__module__]
        except KeyError:
            cls._file = None
        else:
            cls._file = getattr(pymodule, '__file__', None)

            package_name = pymodule.__package__
            if package_name:
                cls._fullname = package_name + '.' + cls.__name__

        if options is not None:
            cls._options = Optuple._new_type_options(cls, options)

    def __call__(_cls, *args, **kwargs):
        try:
            options = _cls._options
        except AttributeError:
            return _cls._factory_call(*args, **kwargs)
        else:
            return options._ellipsis(*args, **kwargs)

    def _instantiate(cls, domain, instance_node):
        if not issubclass(cls, domain.module):
            raise TypeError("Can't instantiate a module of incompatible type")
        return cls._factory_call(domain, instance_node)

    def _factory_call(cls, *args, **kwargs):
        return super(ModuleType, _cls).__call__(*args, **kwargs)

    def __repr__(cls):
        try:
            options = cls._options
        except AttributeError:
            return super(ModuleType, cls).__repr__()
        else:
            return '%s(%r)' % (cls._fullname, ', '.join(options._fields))


class Module(with_metaclass(ModuleType)):
    pass


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

    def __call__(_self, **kwargs):
        return _self._replace(**kwargs) if kwargs else _self

    def __repr__(self):
        return '%s(%s)' % (self._module._name,
                           ', '.join('%s=%r' % pair
                                     for pair in self._iterpairs()))

    def __eq__(self, other):
        return self._type_eq(other) and tuple.__eq__(self, other)
    def __hash__(self):
        return self._type_hash() ^ tuple.__hash__(self)

    #staticmethod, see below
    def __create_base(options,
                      hide_attrs=set(filternot(invoker.startswith('_'),
                                               dir(namedtuple('Empty', []))))):
        ret_type = namedtuple('OptupleBase', map(getter._name, options))

        for bogus_attr in hide_attrs.difference(ret_type._fields):
            setattr(ret_type, bogus_attr, property())

        return ret_type

    __empty_base = __create_base([])
    __create_base = staticmethod(__create_base)

    @classmethod
    def _new_type_options(cls, module, options):
        if not options:
            base_type = cls.__empty_base
        else:
            base_type = cls.__create_base(options)

        new_type = type('Optuple_M%s' % module._name, (cls, base_type),
                        dict(__slots__=(), _module=module))

        make = new_type._make
        new_type._fields   = make(base_type._fields)
        new_type._ellipsis = make(Ellipsis for _ in options)
        new_type._options  = make(map(invoker.set(_module=module), options))

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

        for attr in 'default', 'extendable', '_check_func', '_module':
            if attr in flags:
                setattr(self, attr, flags.pop(attr))

        if 'name' in flags:
            name = flags.pop('name')
            if name.startswith('_'):
                raise ValueError(
                    'Option name cannot start with an underscore: %s' % name)
            self._name = name

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


class MybuildError(Exception):
    """Base class for errors providing a logging-like constructor."""

    def __init__(self, msg, *args, **kwargs):
        if not isinstance(msg, basestring):
            raise TypeError("'msg' argument must be a string")
        if args and kwargs:
            raise TypeError('At most one of args or kwargs can be specified '
                            'at once, not both of them')

        super(MybuildError, self).__init__(msg, args or kwargs or None)

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


