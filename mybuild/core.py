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
    "MybuildError",
]


from collections import namedtuple
from functools import partial
from inspect import getargspec
from operator import attrgetter
import sys

from .util import InstanceBoundTypeMixin

from .util.compat import *


class Module(object):
    """A basic building block of Mybuild."""

    @property
    def _init_func(self):
        return self.instance_type.__init__.im_func  # XXX for now

    def __init__(self, instance_type, options, name=None, pymodule_name=None):
        super(Module, self).__init__()
        self.instance_type = instance_type

        if name is None:
            name = instance_type.__name__
        if pymodule_name is None:
            pymodule_name = instance_type.__module__

        self._init_names(name, pymodule_name)

        class ModuleType(object):
            __slots__ = ()
            _module = self

        self._options = Optuple._new_type_options(ModuleType, options)

    def _init_names(self, name, pymodule_name=None):
        self.__name__ = self._name = name
        self.__module__ = pymodule_name

        if pymodule_name:
            pymodule = sys.modules[pymodule_name]
            package_name = pymodule.__package__
            if package_name:
                self._name = package_name + '.' + name

            self._file = pymodule.__file__
        else:
            self._file = None

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
    def _new_type_options(cls, module_type, options):
        optuple_base = namedtuple('OptupleBase',
                                  (option._name for option in options))

        bogus_attrs = set(a for a in dir(optuple_base)
                          if not a.startswith('_'))
        bogus_attrs.difference_update(optuple_base._fields)
        for attr in bogus_attrs:
            setattr(optuple_base, attr, property())

        new_type = type('Optuple_M%s' % module_type._module._name,
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


