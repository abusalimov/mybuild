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

import logs as log


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

        root.solve(atoms)

        ret = dict.fromkeys(nodes)
        ret.update(root._dict)
        return ret

class DtreeNode(object):
    __slots__ = '_dict', '_decisions'

    def __init__(self, base=None, _dict=None):
        super(DtreeNode, self).__init__()

        base_dict = base._dict if base is not None else None

        if _dict is None:
            _dict = ChainDict(base_dict) if base_dict is not None else {}
        elif _dict.base is not base_dict:
            raise ValueError

        self._dict = _dict
        self._decisions = {}

    def _new_branch(self, _dict=None):
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

    def _itemset(self):
        return set(self._dict.iteritems())

    def solve(self, pnodes):
        with log.debug("dtree: solving %d nodes, %d unset", len(pnodes),
                       len(filter(lambda n: self[n] is None, pnodes))):

            for pnode in pnodes:
                if self[pnode] is None:
                    self._eval(pnode)

            self._master_merge()

    def _eval(self, pnode):
        """Attempt to use proof of contradiction."""

        with log.debug("dtree: evaluating %s", pnode):

            def create_branches():
                for value in True, False:
                    branch = self._new_branch()
                    try:
                        branch[pnode] = value
                    except DtreeConflictError:
                        pass
                    else:
                        yield branch

            branches = tuple(create_branches())

            if not branches:
                log.debug("dtree: no alternatives")
                raise DtreeConflictError

            changeset = branches[0]._itemset()
            if len(branches) == 2:
                # intersect changesets from both branches
                changeset &= branches[1]._itemset()

                log.debug("dtree: two alternatives, %d common values",
                          len(changeset))
                self._decisions[pnode] = branches

            self._merge_changeset(changeset)

    def _master_merge(self):
        decisions = self._decisions
        if not decisions:
            return

        def merge_decision_into_master(master_branches, pnode, branches):
            log.debug("dtree: merge decisions for %s into %d master branches",
                      pnode, len(master_branches))

            for master in master_branches:
                new_branches = master._decisions[pnode] = tuple(
                    master._merge_as_new_branches(branches))

                if len(new_branches) == 1:
                    master._merge_resolved_branches([pnode])
                if new_branches:
                    yield master

        master_pnode, master_branches = decisions.popitem()

        with log.debug("dtree: master merge for %s", master_pnode):
            while decisions:
                master_branches = tuple(merge_decision_into_master(
                    master_branches, *decisions.popitem()))

                if not master_branches:
                    raise DtreeConflictError

            def master_merge_all(branches):
                for master in branches:
                    try:
                        master._master_merge()
                    except DtreeConflictError:
                        pass
                    else:
                        yield master

            master_branches = decisions[master_pnode] = tuple(
                master_merge_all(master_branches))

            if not master_branches:
                raise DtreeConflictError

            if len(master_branches) == 1:
                log.debug("dtree: single master branch left")
                master, = master_branches

                master._dict.update(self._dict)
                master._dict.base = None
                self._dict = master._dict

                self._decisions = master._decisions

    def _merge_as_new_branches(self, branches):
        for branch in branches:
            try:
                changeset = branch._itemset()
                diffitems = changeset and self._diff_for(changeset)
                new_branch = self._new_branch(
                    _dict=ChainDict(self._dict, diffitems))

                for pnode, value in diffitems:
                    pnode.context_setting(new_branch, value)

            except DtreeConflictError:
                pass
            else:
                yield new_branch

    def _merge_changeset(self, changeset, update_dict=True):
        self._merge_resolved_branches(
            self._merge_changeset_resolve(changeset, set(), update_dict))

    def _merge_resolved_branches(self, resolved_pnodes):
        decisions = self._decisions

        while resolved_pnodes:
            branch, = decisions.pop(resolved_pnodes.pop())

            self._merge_changeset_resolve(branch._itemset(), resolved_pnodes)

    def _merge_changeset_resolve(self, changeset, resolved_pnodes,
                                 update_dict=True):
        if not changeset:
            return resolved_pnodes

        diffitems = self._diff_for(changeset)
        if not diffitems:
            return resolved_pnodes

        if update_dict:
            self._dict.update(diffitems)
        else:
            assert all(self[pnode] is value for pnode, value in diffitems)

        decisions = self._decisions

        for pnode, value in diffitems:
            if pnode in decisions:
                branches = decisions[pnode] = tuple(b for b in decisions[pnode]
                                                    if b[pnode] == value)
                if not branches:
                    raise DtreeConflictError

            # This may still throw, I think...
            pnode.context_setting(self, value)

        # Finally propagate the new changeset to branches.

        def merge_propagate(changeset, branches):
            for branch in branches:
                try:
                    branch._merge_changeset(changeset, update_dict=False)
                except DtreeConflictError:
                    pass
                else:
                    yield branch

        for pnode, branches in decisions.iteritems():
            branches = decisions[pnode] = tuple(merge_propagate(diffitems,
                                                               branches))

            if not branches:
                raise DtreeConflictError
            if len(branches) == 1:
                resolved_pnodes.add(pnode)

        return resolved_pnodes

    def _diff_for(self, changeset):
        selfitems = set(self._dict.iteritems())

        # Contains _different_ pairs found in either dict, bot not in both.
        # This means that conflicting items are retained.
        diffitems = selfitems ^ changeset

        if len(dict(diffitems)) < len(diffitems):
            # There are some items with the same key, but different values.
            raise DtreeConflictError

        # Now diffitems holds only items that were not set in the self dict.
        diffitems -= selfitems

        return diffitems


class DtreeError(Exception):
    """Base class for constraints-related errors."""

class DtreeConflictError(DtreeError):
    """Fatal error which leads to dectruction of a Dtree node.

    Raised in case when the reason of an error is constraints violation.
    """

