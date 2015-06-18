"""
Mybuild core types.

TODO docs. -- Eldar
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-09-15"

__all__ = [
    "filter_mtypes",
    "ModuleMetaBase",
    "ModuleBase",
    "Module",
    "CompositeModule",
    "Project",
    "Tool",
    "Optype",
    "OptupleBase",
    "MybuildError",
    "InstanceError",
]


from _compat import *

from collections import namedtuple
from itertools import starmap
from operator import attrgetter
import sys

from util.collections import OrderedDict
from util.itertools import unique_values
from util.operator import attr
from util.operator import getter
from util.operator import invoker
from util.operator import instanceof
from util.prop import default_class_property
from util.prop import cached_property
from util.prop import cached_class_property
from util.misc import InstanceBoundTypeMixin


class ModuleMetaBase(type):
    """Metaclass of Mybuild modules."""

    _opmake  = property(attrgetter('_options._make'))
    _optypes = property(attrgetter('_options._optypes'))
    _optype  = property(attrgetter('_optypes._get'))

    _name = property(getter.__name__)

    @property
    def _fullname(cls):
        if cls.__module__ and cls.__module__ != '__main__':
            quals = cls.__module__.split('.')
            quals[-1] = cls.__name__
            return '.'.join(quals)
        else:
            return cls.__name__

    @property
    def _file(cls):
        return getattr(sys.modules.get(cls.__module__), '__file__', None)

    @property
    def _internal(cls):
        return not hasattr(cls, '_options')

    _base_type = object  # Overridden later to workaround bootstrapping issues.

    def _meta_for_base(cls, **default_kwargs):
        default_kwargs.setdefault('metaclass', type(cls))
        default_kwargs.setdefault('_base_type', cls)
        def meta(name, bases, attrs, **kwargs):
            return new_type(name, bases, attrs, **dict(default_kwargs, **kwargs))
        return meta

    def __new__(mcls, name, bases, attrs, _base_type=None, **kwargs):
        """Suppresses any redundant arguments."""
        if _base_type is None:
            _base_type = mcls._base_type
        if not any(issubclass(base, _base_type) for base in bases):
            bases += (_base_type,)
        return super(ModuleMetaBase, mcls).__new__(mcls, name, bases, attrs)

    def mro(cls):
        new_mro = super(ModuleMetaBase, cls).mro()

        if cls.__mro__ is not None and cls.__mro__ != new_mro:
            if (list(filter_mtypes(cls.__mro__)) !=
                list(filter_mtypes(new_mro))):
                raise NotImplementedError('Dynamic modification '
                                          'of inheritance hierarchy '
                                          'of module types is not supported')

        return new_mro

    def __init__(cls, name, bases, attrs, option_types=None, **kwargs):
        """Real module classes must be created with 'option_types' keyword
        argument or extend some other non-internal class.

        By default produces internal classes.

        Args:
            option_types: A list of ('name', Optype) pairs or None.
        """
        super(ModuleMetaBase, cls).__init__(name, bases, attrs)

        if not cls._internal or option_types is not None:
            option_types = list(option_types or [])

            for option, optype in option_types:
                optype.set(_module=cls, name=option)
                setattr(cls, option, optype)  # acts as a read-only property

            base_option_types = [pair for base in cls._all_mtypes()
                                 for pair in base._optypes._iterpairs()]
            all_optypes = list(unique_values(option_types + base_option_types))

            cls._init_options(all_optypes)

    def _init_options(cls, all_optypes):
        optuple_base = Optuple if all_optypes else EmptyOptuple
        optuple_type = optuple_base._new_type(cls, all_optypes)
        cls._options = optuple_type._options

    def _all_mtypes(cls):
        return tuple(filter_mtypes(cls.__mro__))

    def _instantiate(cls, *args, **kwargs):
        return super(ModuleMetaBase, cls).__call__(*args, **kwargs)

    def __call__(_cls, **kwargs):
        if _cls._internal:
            raise TypeError("Internal class '{_cls}' is not callable"
                            .format(**locals()))
        return _cls._options._ellipsis(**kwargs)

    def __repr__(cls):
        if cls._internal:
            return super(ModuleMetaBase, cls).__repr__()

        options_str = ', '.join(cls._options)
        if options_str:
            options_str = options_str.join('()')

        return cls._fullname + options_str


def filter_mtypes(types, with_internal=False):
    return (cls for cls in types if isinstance(cls, ModuleMetaBase) and
                (with_internal or not cls._internal))


class ModuleBase(extend(metaclass=ModuleMetaBase)):
    """Base class for Mybuild modules."""

    _optuple = property(getter.__optuple)  # read-only even for subtypes

    # These properties default to corresponding class attributes,
    # however instance can override them by setting custom values.
    _name     = default_class_property(getter._name)
    _fullname = default_class_property(getter._fullname)
    _file     = default_class_property(getter._file)

    # ModuleMetaBase overloads __call__, but the default factory call is still
    # available through ModuleMetaBase._instantiate.
    # Note that only non-internal classes can be intantiated.

    def __new__(cls, *args, **kwargs):
        if cls._internal:
            raise TypeError("Can not instantiate internal class '{cls}'"
                            .format(**locals()))
        return super(ModuleBase, cls).__new__(cls)

    def __init__(self, optuple):
        super(ModuleBase, self).__init__()

        if not isinstance(self, optuple._module):
            raise TypeError('Optuple of incompatible module type')
        if not optuple._complete:
            raise ValueError('Incomplete optuple')

        self.__optuple  = optuple

    def __repr__(self):
        return repr(self._optuple)

ModuleMetaBase._base_type = ModuleBase


class Module(ModuleBase):
    """Provides a data necessary for Context."""

    @cached_property
    def tools(self):
        return []

    @cached_property
    def includes(self):
        return []

    # TODO: remove it as redundant
    @cached_property
    def depends(self):
        return []

    @cached_property
    def build_depends(self):
        return []

    @cached_property
    def runtime_depends(self):
        return []

    @cached_class_property
    def provides(cls):
        return [cls]

    @cached_class_property
    def default_provider(cls):
        return None

    @cached_property
    def files(self):
        return []

    def __init__(self, optuple, container=None):
        super(Module, self).__init__(optuple)
        self._container = container

        self._constraints = []  # [(optuple, condition)]

        self.tools = [tool() for tool in self.tools]
        for tool in self.tools:
            for attr, value in iteritems(tool.create_namespaces(self)):
                if not hasattr(self, attr):
                    setattr(self, attr, value)

    def _post_init(self):
        # TODO: remove it as redundant
        for dep in self.depends:
            self._add_constraint(dep)

        for dep in self.build_depends:
            self._add_constraint(dep)

        for interface in self.provides:
            self._discover(interface)

        if self.default_provider is not None:
            self._discover(self.default_provider)

    def _add_constraint(self, mslice, condition=True):
        self._constraints.append((mslice(), condition))

    def _discover(self, mslice):
        self._add_constraint(mslice, condition=False)

    _constrain = _add_constraint


class InterfaceModule(Module):
    provides = []
    default_provider = None

    def __init__(self, optuple, container=None):
        super(InterfaceModule,self).__init__(optuple, container)


class CompositeModule(Module):

    # components = cumulative_sequence_property(attr.__components)

    def _add_component(self, mslice, condition=True):
        self._add_constraint(mslice, condition)


class Project(CompositeModule):
    pass


class Tool(object):
    """docstring for Tool"""

    def create_namespaces(self, instance):
        return {}

    def initialize_module(self, instance):
        pass


class OptupleBase(InstanceBoundTypeMixin):
    __slots__ = ()  # This is essential as far as we overload __dict__.

    _tuple_attrs = frozenset(filternot(invoker.startswith('_'), dir(tuple())))

    # Here __dict__ <-> _asdict() dependence is revesed comparing to
    # an implementation of namedtuple in Python 3.3.
    # This allows subclasses to introduce a regular __dict__ without
    # breaking _asdict() logic.

    @property
    def __dict__(self):
        return self._asdict()

    def _asdict(self):
        'Return a new OrderedDict which maps field names to their values.'
        return OrderedDict(zip(self._fields, self))

    def _instantiate_module(self, *args, **kwargs):
        return self._module._instantiate(self, *args, **kwargs)

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
        for option, value in self._iterpairs(with_ellipsis=with_ellipsis):
            try:
                other_value = getattr(other, option)
            except AttributeError:
                continue
            else:
                yield value, other_value

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
        new_type._optypes  = make(optypes)
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
        assert len(optypes) == 0
        new_type = cls._create_type(cls.__empty_base, module)
        new_type._ellipsis = new_type._optypes = new_type._options = new_type()
        return new_type


class Optype(property):

    def __init__(self, *values, **setup_flags):
        def option_getter(obj):
            # Every module instance has an '_optuple' attribute,
            # see ModuleBase.__init__().
            return getattr(obj._optuple, self._name)
        super(Optype, self).__init__(fget=option_getter)

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

    def all_values(self):
        ret = set()
        for mtype in self._module._all_mtypes():
            try:
                optype = mtype.__dict__[self._name]
            except KeyError:
                continue
            else:
                ret.update(optype._values)
        return ret

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
    def int(cls, default=Ellipsis):
        return cls.of_type(int, default)

    @classmethod
    def of_type(cls, types, default=Ellipsis):
        ret = cls(_check_func=instanceof(types))

        if default is not Ellipsis:
            ret.set(default=default)

        return ret


class MybuildError(Exception):
    """Base class for errors providing a logging-like constructor."""

    def __init__(self, msg='', *args, **kwargs):
        if not isinstance(msg, str):
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


