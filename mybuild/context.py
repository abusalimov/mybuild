"""
Types used on a per-build basis.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-09"

__all__ = ["Context"]


from collections import defaultdict
from collections import deque
from collections import MutableSet
from contextlib import contextmanager
from itertools import izip
from itertools import izip_longest
from itertools import product

import logs as log


class Context(object):
    """docstring for Context"""

    def __init__(self):
        super(Context, self).__init__()
        self._modules = {}
        self._job_queue = deque()
        self._reent_locked = False

    def post(self, fxn):
        self._job_queue.append(fxn)

        with self.reent_lock():
            pass # to flush the queue

    @contextmanager
    def reent_lock(self):
        was_locked = self._reent_locked
        self._reent_locked = True

        try:
            yield
        finally:
            if not was_locked:
                self._job_queue_flush()
            self._reent_locked = was_locked

    def _job_queue_flush(self):
        queue = self._job_queue

        while queue:
            fxn = queue.popleft()
            fxn()

    def consider(self, optuple):
        self.context_for(optuple._module).consider(optuple)

    def register(self, instance):
        self.context_for(instance._module).register(instance)

    def context_for(self, module, option=None):
        try:
            context = self._modules[module]
        except KeyError:
            with self.reent_lock():
                context = self._modules[module] = ModuleContext(self,module)

        return context


class ModuleContext(object):
    """docstring for ModuleContext"""

    def __init__(self, build_ctx, module):
        super(ModuleContext, self).__init__()

        self.build_ctx = build_ctx
        self.module = module

        init_optuple = module._optuple_type._defaults
        self.vsets = init_optuple._make(OptionContext() for _ in init_optuple)

        self.instances = defaultdict(set) # { optuple : { instances... } }

        for a_tuple in izip_longest(*init_optuple, fillvalue=Ellipsis):
            self.consider(a_tuple)

    def consider(self, optuple):
        vsets_optuple = self.vsets

        what_to_extend = ((vset,v)
            for vset,v in izip(vsets_optuple, optuple)
            if v is not Ellipsis and v not in vset)

        for vset_to_extend, value in what_to_extend:
            log.debug('mybuild: extending %r with %r', vset_to_extend, value)
            vset_to_extend.add(value)

            sliced_vsets = (vset if vset is not vset_to_extend else (value,)
                for vset in vsets_optuple)

            for new_tuple in product(*sliced_vsets):
                self.module._instance_type._post_new(self.build_ctx,
                    vsets_optuple._make(new_tuple))

    def register(self, instance):
        self.instances[instance._optuple].add(instance)

    def vset_for(self, option):
        return getattr(self.vsets, option)


class OptionContext(MutableSet):
    """docstring for OptionContext"""

    def __init__(self):
        super(OptionContext, self).__init__()
        self._set = set()
        self._subscribers = []
        self._subscribers_keys = set() # XXX

    def add(self, value):
        if value in self:
            return
        self._set.add(value)

        subscribers = self._subscribers
        self._subscribers = None # our methods are not reenterable

        for s in subscribers:
            s(value)

        self._subscribers = subscribers

    def discard(self, value):
        if value not in self:
            return
        raise NotImplementedError

    def subscribe(self, key, fxn):
        assert key not in self._subscribers_keys
        self._subscribers_keys.add(key)
        self._subscribers.append(fxn)

    def __iter__(self):
        return iter(self._set)
    def __len__(self):
        return len(self._set)
    def __contains__(self, value):
        return value in self._set

    def __repr__(self):
        return '<OptionContext %r>' % (self._set,)

