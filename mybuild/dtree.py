"""
Decision Tree.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-30"

__all__ = [
    "Dtree",
    "DtreeNode",
    "DtreeError",
    "DtreeConflictError",
]


from itertools import izip
from operator import attrgetter

from chaindict import ChainDict


class Dtree(object):

    pdag = property(attrgetter('_pdag'))

    def __init__(self, pdag_):
        super(Dtree, self).__init__()
        self._pdag = pdag_

    def solve(self, initial_values):
        from itertools import permutations

        nodes = self.pdag.nodes
        atoms = self.pdag.atoms
        root = DtreeNode()

        for pnode, value in initial_values.iteritems():
            if pnode not in nodes:
                raise ValueError
            if not isinstance(value, bool):
                raise TypeError

            root[pnode] = value

        root.solve(sorted(nodes, key=lambda n: n not in atoms))

        ret = dict.fromkeys(nodes)
        ret.update(root._dict)
        return ret

class DtreeNode(object):
    __slots__ = '_dict', '_decisions'

    def __init__(self, base=None):
        super(DtreeNode, self).__init__()

        self._dict = ChainDict(base._dict) if base is not None else {}
        self._decisions = {}

    def new_branch(self):
        cls = type(self)
        return cls(base=self)

    def __getitem__(self, pnode):
        try:
            return self._dict[pnode]
        except KeyError:
            return None

    def __setitem__(self, pnode, value):
        assert isinstance(value, bool)

        try:
            old_value = self._dict[pnode]

        except KeyError:
            assert not self._decisions, "NIY"

            self._dict[pnode] = value
            pnode.context_setting(self, value)

        else:
            if old_value != value:
                raise DtreeConflictError

    def _merge_branch(self, branch):
        assert branch._dict.base is self._dict
        assert not branch._decisions, "NIY"

        self._merge_changeset(set(branch._dict.iteritems()))

    def _merge_changeset(self, changeset, update_dict=True):
        self._merge_resolved_branches(
            self._merge_changeset_resolve(changeset, set(), update_dict))

    def _merge_resolved_branches(self, resolved_pnodes):
        decisions = self._decisions

        while resolved_pnodes:
            branch, = decisions.pop(resolved_pnodes.pop())

            self._merge_changeset_resolve(set(branch._dict.iteritems()),
                                          resolved_pnodes)

    def _merge_changeset_resolve(self, changeset, resolved_pnodes,
                                 update_dict=True):
        if not changeset:
            return resolved_pnodes

        selfitems = set(self._dict.iteritems())

        # Contains _different_ pairs found in either dict, bot not in both.
        # This means that conflicting items are retained.
        diff = selfitems ^ changeset

        if len(dict(diff)) < len(diff):
            # There are some items with the same key, but different values.
            raise DtreeConflictError

        # Now diff holds a changeset for branches of ourselves.
        diff -= selfitems

        if update_dict:
            self._dict.update(diff)
        else:
            assert all(self[pnode] is value for pnode, value in diff)

        decisions = self._decisions
        for pnode, value in diff:
            if pnode in decisions:
                branches = decisions[pnode] = tuple(b for b in decisions[pnode]
                                                    if b[pnode] == value)
                if not branches:
                    raise DtreeConflictError

            # This may still throw, I think...
            pnode.context_setting(self, value)

        # Finally propagate the new changeset to branches.

        def merge_into_all(branches):
            for branch in branches:
                try:
                    branch._merge_changeset(diff, update_dict=False)
                except DtreeConflictError:
                    pass
                else:
                    yield branch

        for pnode, branches in decisions.iteritems():
            branches = decisions[pnode] = tuple(merge_into_all(branches))

            if not branches:
                raise DtreeConflictError
            if len(branches) == 1:
                resolved_pnodes.add(pnode)

        return resolved_pnodes

    def solve(self, pnodes):
        for pnode in pnodes:
            # print '>>>>>', pnode.bind(self)
            self.eval(pnode)

    def eval(self, pnode):
        """Attempt to use proof of contradiction."""

        value = self[pnode]

        if value is None:
            def create_branches():
                for value in True, False:
                    branch = self.new_branch()
                    try:
                        branch[pnode] = value
                    except DtreeConflictError:
                        pass
                    else:
                        yield branch

            branches = tuple(create_branches())

            if not branches:
                raise DtreeConflictError

            try:
                the_only_branch, = branches
            except ValueError:
                self._decisions[pnode] = branches
            else:
                self._merge_branch(the_only_branch)

            value = self[pnode]

        return value


class DtreeError(Exception):
    """Base class for constraints-related errors."""

class DtreeConflictError(DtreeError):
    """Fatal error which leads to dectruction of a Dtree node.

    Raised in case when the reason of an error is constraints violation.
    """

