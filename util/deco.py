"""
Useful decorators/deco-makers.
"""
from __future__ import absolute_import


from _compat import *

from collections import deque
import functools
from functools import partial

from util.itertools import pop_iter


def constructor_decorator(*bases, **kwargs):
    """
    Lets using a decorated class as a function decorator, which converts the
    function into a constructor.

    Note: this function returns a fake class which is replaced by the original
    one upon subclassing, thus it doesn't appear in MRO of subclasses. This
    means that the class returned must not be used in super().

    Keyword arguments are passed to a metaclass.
    """

    # For 'cls' itself we define a fake metaclass, which overrides a default
    # __call__ method to accept function objects. On the other hand, it is only
    # used to instantiate the returned class; when subclassing it the metaclass
    # replaces itself with the original one and replaces the returned class
    # with 'cls' with the original __call__ method.
    #
    # This magic is similar to the one used in _compat.extend function.

    class temp_metaclass(type(extend(*bases, **kwargs))):

        def __call__(cls, func):
            # For unknown reasons __doc__ attribute of type objects is
            # read-only, and update_wrapper is unable to set it. The same is
            # about __dict__  attribute which becomes a dictproxy upon class
            # definition, not a dict.
            #
            # So instead we create a new type manually.
            @functools.wraps(func)
            def __init__(self, *args, **kwargs):
                super(ret_type, self).__init__(*args, **kwargs)
                return func(self, *args, **kwargs)

            type_dict = dict(func.__dict__,
                             __module__ = func.__module__,
                             __doc__    = func.__doc__,
                             __init__   = __init__)
            ret_type = type(cls)(func.__name__, (cls,), type_dict)
            return ret_type

    return temp_metaclass('temp_class', None, {})


class defer_call(object):
    """Decorator which remembers calls to a decorated func."""

    def __init__(self, func):
        super(defer_call, self).__init__()
        self.func = func
        self._calls = deque()

    def __call__(self, *args, **kwargs):
        self._calls.append((args, kwargs))

    def call_on(self, target=None):
        if target is None:
            target = self
        for args, kwargs in pop_iter(self._calls, pop_meth='popleft'):
            self.func(target, *args, **kwargs)


def no_reent(func, reent_manager=None):
    """Decorator which defers recursive calls to func to the outermost
    invocation."""
    if reent_manager is None:
        reent_manager = ReentManager()

    @functools.wraps(func)
    def decorated(*args, **kwargs):
        return reent_manager.post(partial(func, *args, **kwargs))
    decorated.no_reent = partial(no_reent, reent_manager=reent_manager)

    return decorated


class ReentManager(object):
    """Job mgmt."""
    __slots__ = '_job_queue', '_outermost'

    def __init__(self):
        super(ReentManager, self).__init__()
        self._job_queue = deque()
        self._outermost = True

    def post(self, func):
        was_outermost = self._outermost
        self._outermost = False

        self._job_queue.append(func)

        if was_outermost:
            try:
                for job_func in pop_iter(self._job_queue, pop_meth='popleft'):
                    job_func()
            finally:
                self._outermost = True

