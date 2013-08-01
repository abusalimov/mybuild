"""
Necessary bindings for Pybuild files.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-29"

__all__ = ['module', 'option']


import functools
import inspect
import threading
from operator import attrgetter

from . import with_defaults
from ..core import ModuleType
from ..core import Module
from ..core import Option

from nsloader import pyfile

from util import constructor_decorator
from util.compat import *


PYFILE_DEFAULTS = ['module', 'option']


class MybuildPyFileLoader(pyfile.PyFileLoader):

    MODULE   = 'PYBUILD'
    FILENAME = 'Pybuild'

    @classmethod
    def init_ctx(cls, ctx, initials=None):
        return super(MybuildPyFileLoader, cls).init_ctx(ctx,
                with_defaults(initials, PYFILE_DEFAULTS, globals()))


class PyFileModuleType(ModuleType):
    """
    Infers options from class constructor. To cancel such behavior, provide a
    keyword argument intermediate=True.
    """

    def __init__(cls, name, bases, attrs, intermediate=False):
        super(PyFileModuleType, cls).__init__(name, bases, attrs,
                options=cls._init_to_options() if not intermediate else None)

    def _init_to_options(cls):
        """Converts a constructor argspec into a list of Option objects."""

        try:
            func = cls.__dict__['__init__']  # to avoid MRO lookup
        except KeyError:
            return []

        if isinstance(func, type(object.__init__)):
            # wrapper descriptor, give up
            return []

        args, va, kw, defaults = inspect.getargspec(func)
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

        head = [Option() for _ in range(len(option_args) - len(defaults))]
        tail = [option if isinstance(option, Option) else Option(option)
                for option in defaults]

        return [option.set(name=name)
                for option, name in zip(head + tail, option_args)]

    _tls = threading.local()
    _tls.instance = None

    def _factory_call(cls, domain, instance_node):
        tls = cls._tls
        if tls.instance is not None:
            raise TypeError('Module instantiation is not reentrant')

        tls.instance = self = cls.__new__(cls)
        try:
            self._instance_init(domain, instance_node)
        finally:
            tls.instance = None
        return self


class PyFileModule(with_metaclass(PyFileModuleType, intermediate=True), Module):

    _context = property(attrgetter('_domain.context'))
    _optuple = property(attrgetter('_domain.optuple'))
    _spawn   = property(attrgetter('_domain.post_new'))

    def _instance_init(self, domain, node):
        self._domain = domain
        self._node = node

        self.__init__(**self._optuple._asdict())

    def consider(self, mslice):
        optuple = mslice()
        module = optuple._module

        consider = self._context.consider

        consider(module)
        for option, value in optuple._iterpairs():
            consider(module, option, value)

    def constrain(self, expr):
        self.consider(expr)
        self._node.add_constraint(expr)

    def provides(self, expr):
        self.consider(expr)
        self._node.add_provided(expr)

    def _decide(self, expr):
        self.consider(expr)
        return self._make_decision(expr)

    def _decide_option(self, mslice, option):
        optuple = mslice()
        module = optuple._module

        def domain_gen(node):
            # This is made through a generator so that in case of replaying
            # everything below (check, subscribing, etc.) is skipped.

            if not hasattr(optuple, option):
                raise AttributeError("'%s' module has no attribute '%s'" %
                                     (module._name, option))

            # Option without the module itself is meaningless.
            self.constrain(optuple)

            def on_domain_extend(new_value):
                # NB: using 'node', not 'self._node'
                _, child_node = node.extend_decisions(module, option,
                                                      new_value)
                self._spawn(child_node)

            option_domain = self._context.domain_for(module, option)
            option_domain.subscribe(on_domain_extend)

            for value in option_domain:
                yield value

        # The 'node' is bound here (the argument of 'domain_gen') because
        # '_make_decision' overwrites 'self._node' with its child.
        return self._make_decision(module, option, domain_gen(self._node))

    def _make_decision(self, module_expr, option=None, domain=(True, False)):
        """
        Returns: a value taken.
        """
        decisions = iter(self._node.make_decisions(module_expr,
                                                   option, domain))

        try:
            # Retrieve the first one (if any) to return it.
            ret_value, self._node = next(decisions)

        except StopIteration:
            raise InstanceError('No viable choice to take')

        # Spawn for the rest ones.
        for _, node in decisions:
            self._spawn(node)

        return ret_value

    def __repr__(self):
        optuple = self._optuple
        node_str = str(self._node)
        return '%s <%s>' % (optuple, node_str) if node_str else str(optuple)

    def build(self, bld):
        src = getattr(self, 'sources', [])
        bld(features='mylink', source=src, target='test')
        print('+++++++++ add task ++++')
        print('module = ' + str(self))
        print('sources = ' + str(src))
        print('+++++++++++++++++++++++')


try:
    from waflib.Task import Task
    from waflib.TaskGen import feature, extension, after_method
    from waflib.Tools import ccroot

    @after_method('process_source')
    @feature('mylink')
    def call_apply_link(self):
        print('linking' + str(self))

    class mylink(ccroot.link_task):
        run_str = 'cat ${SRC} > ${TGT}'

    class ext2o(Task):
        run_str = 'cp ${SRC} ${TGT}'

    @extension('.c')
    def process_ext(self, node):
        self.create_compiled_task('ext2o', node)

except ImportError:
    pass  # XXX move Waf-related stuff from here

class ModuleInspector(object):

    def __init__(self, owner, optuple):
        super(PyFileModule._InstanceProxy, self).__init__()
        self._owner = owner
        self._optuple = optuple

    def __nonzero__(self):
        return self._owner._decide(self._optuple)

    def __getattr__(self, attr):
        return self._owner._decide_option(self._optuple, attr)


module = constructor_decorator(PyFileModule, __doc__=
    """
    Example of a simple module without any options:

    >>> @module
    ... def modname(self):
    ...     pass

    More examples:

    >>> @module
    ... def m(self,
    ...       foo = option(0, 'one', 'two'),    # one of these, or any other
    ...       bar = option.enum(38400, 115200), # enumeration of two values
    ...       baz = option.bool(default=True),  # boolean flag
    ...         ):
    ...     pass

    >>> class modclass(module):
    ...     def __init__(self, opt = option.bool()):
    ...         pass

    """)

option = Option

if __name__ == '__main__':
    import doctest
    doctest.testmod()

