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

    def __init__(self, base=None, _dict=None):
        super(DtreeNode, self).__init__()

        if _dict is None:
            _dict = ChainDict(base._dict) if base is not None else {}
        elif _dict.base is not base:
            raise ValueError

        self._dict = _dict
        self._decisions = {}

    def new_branch(self, _dict=None):
        cls = type(self)
        return cls(base=self, _dict=_dict)

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

    def solve(self, pnodes):
        for pnode in pnodes:
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

            changeset = set(branches[0]._dict.iteritems())
            if len(branches) == 2:
                # intersect changesets from both branches
                changeset &= set(branches[1]._dict.iteritems())

                self._decisions[pnode] = branches

            self._merge_changeset(changeset)

            value = self[pnode]

        return value

    def _merge_to_master_decision(self):
        decisions = self._decisions
        if not decisions:
            return

        master_branches = decisions.popitem()[1]

        for pnode, branches in decisions.iteritems():
            assert len(branches) == 2

        # self._merge_changeset(set(branch._dict.iteritems()))

    def _merge_branch(self, branch):
        assert branch._dict.base is self._dict
        assert not branch._decisions, "NIY"

        self._merge_changeset(set(branch._dict.iteritems()))

    def _merge_changeset(self, changeset,
                         decision_pnode=None, update_dict=True):
        self._merge_resolved_branches(
            self._merge_changeset_resolve(changeset, set(),
                                          decision_pnode, update_dict))

    def _merge_resolved_branches(self, resolved_pnodes):
        decisions = self._decisions

        while resolved_pnodes:
            branch, = decisions.pop(resolved_pnodes.pop())

            self._merge_changeset_resolve(set(branch._dict.iteritems()),
                                          resolved_pnodes)

    def _merge_changeset_resolve(self, changeset, resolved_pnodes,
                                 decision_pnode=None, update_dict=True):
        if not changeset:
            return resolved_pnodes

        selfdict = self._dict
        selfitems = set(selfdict.iteritems())

        # Contains _different_ pairs found in either dict, bot not in both.
        # This means that conflicting items are retained.
        diffitems = selfitems ^ changeset
        diffdict = ChainDict(selfdict, diffitems)

        if len(diffdict) < len(diffitems):
            # There are some items with the same key, but different values.
            raise DtreeConflictError

        # Now diffitems holds a changeset for branches of ourselves, if any.
        diffitems -= selfitems
        if not diffitems:
            return resolved_pnodes

        decisions = self._decisions
        if decision_pnode is not None:
            new_branch = self.new_branch(_dict=diffdict)

            try:
                decisions[decision_pnode] += new_branch
            except KeyError:
                decisions[decision_pnode] = new_branch
            else:
                assert len(decisions[decision_pnode]) <= 2

            return

        if update_dict:
            self._dict.update(diffdict)
        else:
            assert all(self[pnode] is value for pnode, value in diffitems)

        for pnode, value in diffitems:
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
                    branch._merge_changeset(diffitems, update_dict=False)
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


class DtreeError(Exception):
    """Base class for constraints-related errors."""

class DtreeConflictError(DtreeError):
    """Fatal error which leads to dectruction of a Dtree node.

    Raised in case when the reason of an error is constraints violation.
    """

