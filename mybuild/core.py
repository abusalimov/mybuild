"""
Mybuild core types.

TODO docs. -- Eldar
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-09-15"

__all__ = [
    "ModuleMeta",
    "Module",
    "Optype",
    "Optuple",
    "MybuildError",
    "InstanceError",
]


from _compat import *

from collections import namedtuple
from itertools import starmap
from operator import attrgetter
import sys

from util.operator import getter
from util.operator import invoker
from util.operator import instanceof
from util.prop import class_default_property
from util.misc import InstanceBoundTypeMixin


class ModuleMeta(type):
    """Metaclass of Mybuild modules."""

    _opmake  = property(attrgetter('_options._make'))
    _optypes = property(attrgetter('_options._optypes'))
    _optype  = property(attrgetter('_optypes._get'))

    _name = property(getter.__name__)

    @property
    def _fullname(cls):
        if cls.__module__:
            return cls.__module__ + '.' + cls.__name__
        else:
            return cls.__name__

    @property
    def _file(cls):
        return getattr(sys.modules.get(cls.__module__), '__file__', None)

    @property
    def _internal(cls):
        return not hasattr(cls, '_options')

    def __new__(mcls, name, bases, attrs, **kwargs):
        """Suppresses any redundant arguments."""
        return super(ModuleMeta, mcls).__new__(mcls, name, bases, attrs)

    def __init__(cls, name, bases, attrs, internal=False, **kwargs):
        """Auxiliary internal classes must be created with internal=True
        keyword metaclass argument.

        The rest keywords are passed to _prepare_optypes method."""
        super(ModuleMeta, cls).__init__(name, bases, attrs)

        if not internal:
            if hasattr(cls, '_options'):
                raise TypeError("A non-internal class '{cls}' already has "
                                "an '_options' attribute".format(**locals()))
            cls._init_options(cls._prepare_optypes(**kwargs))

    def _prepare_optypes(cls, optypes):
        return optypes

    def _init_options(cls, optypes):
        optuple_type = Optuple if optypes else EmptyOptuple
        cls._options = options = optuple_type._new_type(cls, optypes)._options

        for option in options:
            # Every module has an _optuple attribute, see Module.__new__
            getter = attrgetter('_optuple.{0}'.format(option))
            setattr(cls, option, property(getter))

    def __call__(_cls, **kwargs):
        if _cls._internal:
            raise TypeError("Internal class '{_cls}' is not callable"
                            .format(**locals()))
        return _cls._options._ellipsis(**kwargs)

    def _instantiate(cls, optuple):
        instance = cls.__new__(cls, optuple)
        if isinstance(instance, cls):
            instance.__init__(**optuple._asdict())
        return instance

    def __repr__(cls):
        if cls._internal:
            return super(ModuleMeta, cls).__repr__()

        options_str = ', '.join(cls._options)
        if options_str:
            options_str = options_str.join('()')

        return cls._fullname + options_str


class ModuleBase(extend(metaclass=ModuleMeta, internal=True)):
    """Base class for Mybuild modules."""

    # This is read-only even for subtypes.
    _optuple  = property(getter.__optuple)

    # These properties default to corresponding class ones,
    # however instance is allowed to override them by setting custom values.
    _name     = class_default_property(getter._name)
    _fullname = class_default_property(getter._fullname)
    _file     = class_default_property(getter._file)

    # ModuleMeta overloads __call__, but the default factory call is
    # available through ModuleMeta._instantiate with the only exception
    # that __init__  is called with optuple unpacked into keyword arguments,
    # unlike __new__ which receives the sole optuple argument.

    def __new__(cls, optuple):
        if cls._internal:
            raise TypeError('Internal module class')
        if not issubclass(cls, optuple._module):
            raise TypeError('Optuple of incompatible module type')
        if not optuple._complete:
            raise ValueError('Incomplete optuple')

        new = super(Module, cls).__new__(cls)
        new.__optuple  = optuple
        return new

    def __init__(_self, **kwargs):
        """Consumes keyword arguments."""
        super(Module, _self).__init__()

    def __repr__(self):
        return repr(self._optuple)


class Module(extend(ModuleBase, internal=True)):
    """Delegates requests to any unknown attributes to another object."""

    _delegate = property(getter.__delegate)

    def __new__(cls, optuple, delegate=None):
        new = super(Module, cls).__new__(cls, optuple)
        new.__delegate = delegate
        return new

    def __getattr__(self, attr):
        try:
            return getattr(self._delegate, attr)
        except AttributeError as e:
            e.args = ("'{cls.__name__}' object has no attribute '{attr}', "
                      "nor has its '{dcls.__name__}' delegate"
                      .format(cls=type(self), dcls=type(self._delegate),
                              **locals())),)
            raise e


class OptupleBase(InstanceBoundTypeMixin):

    _tuple_attrs = frozenset(filternot(invoker.startswith('_'), dir(tuple())))

    def __call__(_self, **kwargs):
        return _self._replace(**kwargs) if kwargs else _self

    def __eq__(self, other):
        return self._type_eq(other) and tuple.__eq__(self, other)
    def __hash__(self):
        return self._type_hash() ^ tuple.__hash__(self)

    def __repr__(self):
        options_str = ', '.join(starmap('{0}={1}'.format, self._iterpairs()))
        if options_str:
            options_str = options_str.join('()')

        return self._module._fullname + options_str

    @classmethod
    def _create_type(cls, base_type, module):
        return type('ModuleOptuple', (cls, base_type),
                    dict(__slots__=(), _module=module))


class Optuple(OptupleBase):
    """Option tuple mixin type."""
    __slots__ = ()

    @property
    def _complete(self):
        return Ellipsis not in self

    def _iter(self, with_ellipsis=False):
        return (iter(self) if with_ellipsis else
                (v for v in self if v is not Ellipsis))

    def _iterpairs(self, with_ellipsis=False):
        it = zip(self._options, self)
        return (it if with_ellipsis else
                (pair for pair in it if pair[1] is not Ellipsis))

    def _zipwith(self, other, with_ellipsis=False):
        it = zip(self, other)
        return (it if with_ellipsis else
                (pair for pair in it if pair[0] is not Ellipsis))

    def _get(self, attr):
        return getattr(self, attr)

    def _replace(_self, **kwargs):
        def iter_new_values(option, old_value):
            try:
                new_value = kwargs.pop(option)
            except KeyError:
                return old_value
            else:
                if old_value is not Ellipsis:
                    raise ValueError("Option '%s' redefined from %r to %r" %
                                     (option, old_value, new_value))
                return new_value

        result = _self._make(map(iter_new_values, _self._fields, _self))
        if kwargs:
            raise ValueError('Got unexpected option names: %r' % kwargs.keys())

        return result

    @classmethod
    def _new_type(cls, module, optypes):
        base_type = namedtuple('Optuple', map(getter._name, optypes))

        for bogus_attr in cls._tuple_attrs.difference(base_type._fields):
            setattr(base_type, bogus_attr, property())

        new_type = cls._create_type(base_type, module)

        make = new_type._make
        new_type._ellipsis = make(Ellipsis for _ in optypes)
        new_type._optypes  = make(map(invoker.set(_module=module), optypes))
        new_type._options  = make(new_type._fields)

        return new_type


class EmptyOptuple(OptupleBase):
    """Option tuple mixin type."""
    __slots__ = ()

    @property
    def _complete(self):
        return True

    def _iter(self, with_ellipsis=False):
        return iter(())

    def _iterpairs(self, with_ellipsis=False):
        return iter(())

    def _zipwith(self, other, with_ellipsis=False):
        return iter(())

    def _get(self, attr):
        raise AttributeError('Empty optuple has no options')

    def _replace(_self, **kwargs):
        if kwargs:
            raise ValueError('Got unexpected option names: %r' % kwargs.keys())
        return _self

    def __repr__(self):
        return self._module._fullname

    __empty_base = namedtuple('EmptyOptuple', [])
    for bogus_attr in OptupleBase._tuple_attrs:
        setattr(__empty_base, bogus_attr, property())

    @classmethod
    def _new_type(cls, module, optypes):
        assert not optypes
        new_type = cls._create_type(cls.__empty_base, module)
        new_type._ellipsis = new_type._optypes = new_type._options = new_type()
        return new_type


class Optype(object):

    def __init__(self, *values, **setup_flags):
        super(Optype, self).__init__()

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
        ret = cls(_check_func=instanceof(types))

        if default is not Ellipsis:
            ret.set(default=default)

        return ret


class MybuildError(Exception):
    """Base class for errors providing a logging-like constructor."""

    def __init__(self, msg='', *args, **kwargs):
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


class InstanceError(MybuildError):
    """
    Throwing this kind of errors from inside a module function indicates that
    instance is not viable anymore and thus shouldn't be considered.
    """


