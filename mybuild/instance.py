"""
Everything related to running @module functions.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-12-14"


from collections import defaultdict
from itertools import chain
from operator import attrgetter

from .core import MybuildError
from .pgraph import *
from util import bools

from util.compat import *


class InstanceNodeBase(object):
    __slots__ = '_parent', '_childmap'

    parent = property(attrgetter('_parent'))

    def __init__(self, parent=None):
        super(InstanceNodeBase, self).__init__()

        self._parent = parent
        self._childmap = defaultdict(dict)

    def get_child(self, key, value):
        return self._childmap[key][value]

    def _create_children(self, key, *values):
        vmap = self._childmap[key]

        for value in values:
            if value in vmap:
                raise ValueError
            vmap[value] = self._new_child(key, value)

        return (vmap[value] for value in values)

    def _new_child(self, parent_key=None, parent_value=None):
        cls = type(self)
        return cls(parent=self)

    def iter_children(self, key):
        return iteritems(self._childmap[key])


class InstanceNode(InstanceNodeBase):
    __slots__ = '_constraints', '_provideds', '_decisions'

    def __init__(self, parent=None):
        super(InstanceNode, self).__init__(parent)
        self._constraints = []
        self._provideds = []
        self._decisions = {}

    def _new_child(self, parent_key=None, parent_value=None):
        new = super(InstanceNode, self)._new_child(parent_key, parent_value)

        new._decisions.update(self._decisions)

        assert parent_key not in new._decisions
        new._decisions[parent_key] = parent_value

        return new

    def add_constraint(self, expr):
        self._constraints.append(expr)

    def add_provided(self, expr):
        self._provideds.append(expr)

    def make_decisions(self, module_expr, option=None, values=bools):
        """
        Either retrieves an already taken decision (in case of replaying),
        or creates a new child for each value from 'values' iterable returning
        list of the resulting pairs.

        Returns: (value, node) pairs iterable.
        """
        key = module_expr, option

        try:
            value = self._decisions[key]

        except KeyError:
            values = tuple(values)
            return zip(values, self._create_children(key, *values))

        else:
            return [(value, self)]

    def extend_decisions(self, module, option, value):
        key = module, option
        child, = self._create_children(key, value)
        return value, child

    def _cond_pnode(self, g, module_expr, option, value):
        if option is not None:
            # module_expr is definitely a plain module here
            pnode = g.atom_for(module_expr, option, value)

        else:
            # here value is bool
            pnode = g.pnode_for(module_expr)
            if not value:
                pnode = Not(g, pnode)

        return pnode

    def create_pnode(self, g):
        def iter_conjuncts():
            for (module_expr, option), vmap in iteritems(self._childmap):
                for value, child in iteritems(vmap):

                    yield Implies(g,
                        self._cond_pnode(g, module_expr, option, value),
                        child.create_pnode(g))

        return And(g, *chain(map(g.pnode_for, self._constraints),
                             iter_conjuncts()))

    def create_decisions_pnode(self, g):
        def iter_conjuncts():
            for (module_expr, option), value in iteritems(self._decisions):
                yield self._cond_pnode(g, module_expr, option, value)

        return And(g, *iter_conjuncts())

    def __repr__(self):
        return ', '.join('%s%s=%s' %
                    (module, '.' + option if option else '', value)
                for (module, option), value in iteritems(self._decisions))


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

class InstanceError(MybuildError):
    """
    Throwing this kind of errors from inside a module function indicates that
    instance is not viable anymore and thus shouldn't be considered.
    """

