"""
Decision Tree.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-30"

__all__ = [
    "Dtree",
    "DtreeNode",
]


from itertools import izip
from itertools import repeat
from operator import attrgetter
from operator import methodcaller

from chaindict import ChainDict
from pdag import PdagContext
from pdag import PdagContextError
from util import filter_bypass
from util import map_bypass

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
        root.solve(atoms, initial_values)

        ret = dict.fromkeys(nodes)
        ret.update(root._dict)
        return ret

class DtreeNode(PdagContext):
    __slots__ = '_dict', '_branchmap', '_pending_resolve'

    def __init__(self, base=None):
        super(DtreeNode, self).__init__()

        self._dict = ChainDict(base._dict) if base is not None else {}
        self._branchmap = {}
        self._pending_resolve = set()

    def _new_branch(self):
        cls = type(self)
        return cls(base=self)

    def _new_branch_with(self, pnode, value):
        branch = self._new_branch()
        branch[pnode] = value
        return branch

    def _new_branch_from(self, changeset):
        branch = self._new_branch()

        diffitems = changeset and self._diff_for(changeset)
        if diffitems:
            branch._dict.update(diffitems)

            for pnode, value in diffitems:
                pnode.context_setting(branch, value)

        return branch

    def solve(self, pnodes, initial_values):
        with log.debug("dtree: solving %d nodes", len(pnodes)):

            for pnode, value in initial_values.iteritems():
                if not isinstance(value, bool):
                    raise TypeError

                self[pnode] = value

            for pnode in pnodes:
                if self[pnode] is None:
                    self._create_branches_on(pnode)

            self._master_merge()

    def _create_branches_on(self, pnode):
        """Attempt to use proof of contradiction."""

        with log.debug("dtree: branching on %s", pnode):

            branches = map_bypass(self._new_branch_with, PdagContextError,
                                  repeat(pnode), (True, False))

            if not branches:
                log.debug("dtree: no alternatives")
                raise PdagContextError

            changeset = branches[0]._itemset()
            if len(branches) == 2:
                # intersect changesets from both branches
                changeset &= branches[1]._itemset()

                log.debug("dtree: two alternatives, %d common values",
                          len(changeset))
                self._branchmap[pnode] = branches

            if changeset:
                self._merge_changeset(changeset)

    def _master_merge(self):
        branchmap = self._branchmap
        if not branchmap:
            return

        master_pnode, master_branches = branchmap.popitem()

        with log.debug("dtree: master merge for %s", master_pnode):
            while branchmap:
                pnode, branches = branchmap.popitem()
                master_branches = filter_bypass(
                    methodcaller('_merge_as_branches_on', pnode, branches),
                    PdagContextError, master_branches)

                if not master_branches:
                    raise PdagContextError

            master_branches = branchmap[master_pnode] = filter_bypass(
                methodcaller('_master_merge'),
                PdagContextError, master_branches)

            if not master_branches:
                raise PdagContextError

            if len(master_branches) == 1:
                log.debug("dtree: single master branch left")
                master, = master_branches

                master._dict.update(self._dict)
                master._dict.base = None
                self._dict = master._dict

                self._branchmap = master._branchmap

    def _merge_as_branches_on(self, pnode, branches):
        new_branches = self._branchmap[pnode] = map_bypass(
            self._new_branch_from, PdagContextError,
            (branch._itemset() for branch in branches))

        if not new_branches:
            raise PdagContextError

        elif len(new_branches) == 1:
            self._pending_resolve.add(pnode)
            self._merge_resolved_branches()

    def _merge_changeset(self, changeset, update_dict=True):
        self._merge_changeset_resolve(changeset, update_dict)
        self._merge_resolved_branches()

    def _merge_resolved_branches(self):
        branchmap = self._branchmap

        resolved_pnodes = self._pending_resolve
        while resolved_pnodes:
            branch, = branchmap.pop(resolved_pnodes.pop())

            self._merge_changeset_resolve(branch._itemset())

    def _merge_changeset_resolve(self, changeset, update_dict=True):
        diffitems = changeset and self._diff_for(changeset)
        if not diffitems:
            return

        if update_dict:
            self._dict.update(diffitems)

        else:
            # Not sure if this is ever useful.
            for pnode, value in changeset - diffitems:
                assert self._dict[pnode] == value
                del self._dict[pnode]

            assert all(self[pnode] == value for pnode, value in changeset)

        branchmap = self._branchmap

        for pnode, value in diffitems:
            # If the pnode has been used for branching then prune a bad one.
            if pnode in branchmap:
                branches = branchmap[pnode] = list(b for b in branchmap[pnode]
                                                   if b[pnode] == value)
                if not branches:
                    raise PdagContextError

            # This may still throw, I think...
            pnode.context_setting(self, value)

        # Finally propagate the new changeset to branches.

        resolved_pnodes = self._pending_resolve

        for pnode, branches in branchmap.iteritems():
            branches = branchmap[pnode] = filter_bypass(
                methodcaller('_merge_changeset', changeset, update_dict=False),
                PdagContextError, branches)

            if not branches:
                raise PdagContextError
            if len(branches) == 1:
                resolved_pnodes.add(pnode)

    def _diff_for(self, changeset):
        selfitems = self._itemset()

        # Contains _different_ pairs found in either dict, bot not in both.
        # This means that conflicting items are retained.
        diffitems = selfitems ^ changeset

        if len(dict(diffitems)) < len(diffitems):
            # There are some items with the same key, but different values.
            raise PdagContextError

        # Now diffitems holds only items that were not set in the self dict.
        diffitems -= selfitems

        return diffitems

    def _itemset(self):
        return set(self._dict.iteritems())


