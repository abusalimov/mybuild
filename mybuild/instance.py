"""
Everything related to running @module functions.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-12-14"


from collections import defaultdict
from itertools import izip
from operator import attrgetter


class InstanceDomain(object):

    context = property(attrgetter('_context'))
    optuple = property(attrgetter('_optuple'))

    _init_fxn = property(attrgetter('_optuple._module._init_fxn'))

    def __init__(self, context, optuple):
        super(InstanceDomain, self).__init__()
        self._context = context
        self._optuple = optuple

        self._instances = []
        self._node = root_node = InstanceNode()

        self.post_new(root_node)

    def post_new(self, node):
        instance = Instance(self, node)

        def new():
            with log.debug("mybuild: new %r", self):
                try:
                    self._init_fxn(*optuple)
                except InstanceError as e:
                    log.debug("mybuild: unviable %r: %s", self, e)
                else:
                    log.debug("mybuild: succeeded %r", self)
                    self._instances.append(instance)

        self._context.post(new)

    def create_pnode(self):
        return self._node.create_pnode(self._context)


class InstanceNodeBase(object):
    __slots__ = '_parent', '_childmap'

    parent = property(attrgetter('_parent'))

    def __init__(self, parent=None):
        super(TreeNode, self).__init__()

        self._parent = parent
        self._childmap = {}

    def get_child(self, key, value):
        return self._childmap[key][value]

    def _create_children(self, key, values):
        try:
            mapping = self._childmap[key]
        except KeyError:
            mapping = self._childmap[key] = {}

        for value in values:
            if value in mapping:
                raise ValueError
            mapping[value] = self._new_child(key, value)

        return (mapping[value] for value in values)

    def create_child(self, key, value):
        child, = self._create_children(key, (value,))
        return child

    def _new_child(self, parent_key=None, parent_value=None):
        cls = type(self)
        return cls(parent=self)

    def iter_children(self, key):
        return self._childmap[key].iteritems()


class InstanceNode(InstanceNodeBase):
    __slots__ = '_constraints', '_decisions'

    def __init__(self, parent=None):
        super(InstanceNode, self).__init__(parent)
        self._constraints = set()
        self._decisions = {}

    def _new_child(self, parent_key=None, parent_value=None):
        new = super(InstanceNode, self)._new_child(parent_key, parent_value)

        new._decisions.update(self._decisions)

        assert parent_key not in new._decisions
        new._decisions[parent_key] = parent_value

        return new

    def constrain(self, expr):
        self._node._constraints.add(expr)

    def make_decisions(self, key, values):
        """
        Either retrieves an already taken decision (in case of replaying),
        or creates a new child for each value from 'values' iterable returning
        list of the resulting pairs.

        Returns: (value, node) pairs iterable.
        """

        try:
            value = self._decisions[key]

        except KeyError:
            values = tuple(values)
            return izip(values, self._create_children(key, values))

        else:
            return ((value, self),)

    def create_pnode(self, context):
        # def iter_conjuncts():
        #     for expr in self._constraints:
        #         yield context.ato_for(expr)
        pass


class Instance(object):

    class _InstanceProxy(object):
        __slots__ = '_owner', '_optuple'

        def __init__(self, owner, optuple):
            super(Instance._InstanceProxy, self).__init__()
            self._owner = owner
            self._optuple = optuple

        def __nonzero__(self):
            return self._owner._decide(self._optuple)

        def __getattr__(self, attr):
            return self._owner._decide_option(self._optuple, attr)

    _context = property(attrgetter('_domain.context'))
    _optuple = property(attrgetter('_domain.optuple'))
    _spawn   = property(attrgetter('_domain.post_new'))

    def __init__(self, domain, node):
        super(Instance, self).__init__()
        self._domain = domain
        self._node = node

    def consider(self, expr):
        # self._context.consider
        pass

    def constrain(self, expr):
        self.consider(expr)
        self._node.constrain(expr)

    def _decide(self, mslice):
        dkey = mslice, None
        return self._make_decision(dkey, (False, True))

    def _decide_option(self, mslice, option):
        dkey = mslice, option
        module = mslice._module

        def domain_gen():
            if not hasattr(mslice, option):
                raise AttributeError("'%s' module has no attribute '%s'" %
                                     (module._name, option))

            option_domain = self._context.domain_for(module, option)

            # Need to save the currnet node here
            # because _make_decision overwrites it with its child.
            saved_self_node = self._node
            option_domain.subscribe(lambda new_value:
                self._spawn(saved_self_node.create_child(dkey, new_value)))

            for value in option_domain:
                yield value

        return self._make_decision(dkey, domain_gen())

    def _make_decision(self, dkey, domain):
        """
        Returns: a value taken.
        """
        value_node_pairs = iter(self._node.make_decisions(dkey, domain))

        try:
            # Retrieve the first one (if any) to return it.
            ret_value, self._node = value_node_pairs.next()

        except StopIteration:
            raise InstanceError('No viable choice to take')

        else:
            log.debug('mybuild: take %s=%s', dkey, ret_value)

        # Spawn for the rest ones.
        spawn = self._spawn
        for _, node in value_node_pairs:
            spawn(node)

        return ret_value

