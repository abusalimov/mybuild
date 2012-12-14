"""
Everything related to running @module functions.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-12-14"


from collections import defaultdict
from operator import attrgetter


class InstanceDomain(object):
    def __init__(self, context, optuple):
        super(InstanceDomain, self).__init__()
        self._context = context
        self._optuple = optuple

        self._instances = []
        self._node = root_node = InstanceNode()

        self.post_new(root_node)

    def post_new(self, node, _decisions=None):
        instance = Instance(self, node, _decisions)

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

class InstanceNodeBase(object):
    __slots__ = '_parent', '_childmap'

    parent = property(attrgetter('_parent'))

    def __init__(self):
        super(TreeNode, self).__init__()

        self._parent = None
        self._childmap = {}

    def create_children(self, key, *values):
        try:
            mapping = self._childmap[key]
        except KeyError:
            mapping = self._childmap[key] = {}

        for value in values:
            if value in mapping:
                raise ValueError
            child = mapping[value] = self._new_child(key, value)

    def _new_child(self, parent_key=None, parent_value=None):
        cls = type(self)
        new = cls()
        new._parent = self
        return new

    def iter_children(self, key):
        return self._childmap[key].iteritems()


class InstanceNode(InstanceNodeBase):
    __slots__ = 'constraints', 'decisions'

    def __init__(self):
        super(InstanceNode, self).__init__()
        self.constraints = set()
        self.decisions = {}

    def _from_parent(self, parent_key=None, parent_value=None):
        new = super(InstanceNode, self)._new_child(parent_key, parent_value)
        new.decisions[parent_key] = parent_value
        return new

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

    def __init__(self, domain, node, _decisions=None):
        super(Instance, self).__init__()
        self._domain = domain
        self._node = node
        self._decisions = _decisions if _decisions is not None else {}

    def consider(self, expr):
        pass # XXX

    def constrain(self, expr):
        self.consider(expr)
        self._node.constraints.add(expr)

    def _decide(self, mslice):
        dkey = mslice, None

        try:
            return self._decisions[dkey]

        except KeyError:
            node = self._node
            node.create_children(dkey, False, True)

            taken = self._take_one_spawn_rest(dkey, node.iter_children(dkey))
            ret_value, self._node = taken

            assert ret_value is self._decisions[dkey]
            return ret_value

    def _decide_option(self, mslice, option):
        dkey = mslice, option
        module = mslice._module

        try:
            return self._decisions[dkey]

        except KeyError:
            if not hasattr(mslice, option):
                raise AttributeError("'%s' module has no attribute '%s'" %
                                     (module._name, option))

            # Option without the module itself is meaningless.
            self.constrain(module)

            option_domain = self._domain.context.domain_for(module, option)

            def on_domain_expand(new_value):
                self._node.create_children(dkey, new_value)

                new_decisions = saved_decisions.copy()
                new_decisions[decision_key] = new_value

                self._domain.post_new(node, new_decisions)

                self._spawn(constraints)

            option_domain.subscribe(on_domain_expand)

            node = self._node
            node.create_children(dkey, *option_domain)

            taken = self._take_one_spawn_rest()

            ret_value = self._constraints.get(module, option) # must not throw

            log.debug('mybuild: return %r', ret_value)
            return ret_value

    def _take_one_spawn_rest(self, decision_key, value_node_iterable):
        """
        Returns: (value, node) tuple.
        """
        try:
            # Retrieve the first one (if any) to return it.
            value, node = value_node_iterable.next()

        except StopIteration:
            raise InstanceError('No viable choice to take')

        log.debug('mybuild: take %s=%s', decision_key, value)
        self._decisions[decision_key] = value

        # Spawn for the rest ones.
        self._spawn_all(value_node_iterable)

        return value, node

    def _spawn_all(self, decision_key, value_node_iterable):
        for value, node in value_node_iterable:
            self._spawn(decision_key, value, node)

    def _spawn(self, decision_key, value, node):
        log.debug('mybuild: spawn %s=%s', decision_key, value)

        new_decisions = self._decisions.copy()
        new_decisions[decision_key] = value

        self._domain.post_new(node, new_decisions)


