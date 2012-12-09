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
from operator import attrgetter

from chaindict import ChainDict
from pdag import PdagContext
from pdag import PdagContextError

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

    def _itemset(self):
        return set(self._dict.iteritems())

    def solve(self, pnodes, initial_values):
        with log.debug("dtree: solving %d nodes", len(pnodes)):

            for pnode, value in initial_values.iteritems():
                if not isinstance(value, bool):
                    raise TypeError

                self[pnode] = value

            for pnode in pnodes:
                if self[pnode] is None:
                    self._branch_on(pnode)

            self._master_merge()

    def _branch_on(self, pnode):
        """Attempt to use proof of contradiction."""

        with log.debug("dtree: branching on %s", pnode):

            def create_branches():
                for value in True, False:
                    branch = self._new_branch()
                    try:
                        branch[pnode] = value
                    except PdagContextError:
                        pass
                    else:
                        yield branch

            branches = tuple(create_branches())

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

        def merge_decision_into_master(master_branches, pnode, branches):
            log.debug("dtree: merge branches for %s into %d master branches",
                      pnode, len(master_branches))

            for master in master_branches:
                new_branches = master._branchmap[pnode] = tuple(
                    master._merge_as_new_branches(branches))

                if len(new_branches) == 1:
                    master._pending_resolve.add(pnode)
                    master._merge_resolved_branches()
                if new_branches:
                    yield master

        master_pnode, master_branches = branchmap.popitem()

        with log.debug("dtree: master merge for %s", master_pnode):
            while branchmap:
                master_branches = tuple(merge_decision_into_master(
                    master_branches, *branchmap.popitem()))

                if not master_branches:
                    raise PdagContextError

            def master_merge_all(branches):
                for master in branches:
                    try:
                        master._master_merge()
                    except PdagContextError:
                        pass
                    else:
                        yield master

            master_branches = branchmap[master_pnode] = tuple(
                master_merge_all(master_branches))

            if not master_branches:
                raise PdagContextError

            if len(master_branches) == 1:
                log.debug("dtree: single master branch left")
                master, = master_branches

                master._dict.update(self._dict)
                master._dict.base = None
                self._dict = master._dict

                self._branchmap = master._branchmap

    def _merge_as_new_branches(self, branches):
        for branch in branches:
            try:
                changeset = branch._itemset()
                diffitems = changeset and self._diff_for(changeset)

                new_branch = self._new_branch()
                new_branch._dict.update(diffitems)

                for pnode, value in diffitems:
                    pnode.context_setting(new_branch, value)

            except PdagContextError:
                pass
            else:
                yield new_branch

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
                branches = branchmap[pnode] = tuple(b for b in branchmap[pnode]
                                                    if b[pnode] == value)
                if not branches:
                    raise PdagContextError

            # This may still throw, I think...
            pnode.context_setting(self, value)

        # Finally propagate the new changeset to branches.

        def merge_propagate(changeset, branches):
            for branch in branches:
                try:
                    branch._merge_changeset(changeset, update_dict=False)
                except PdagContextError:
                    pass
                else:
                    yield branch

        resolved_pnodes = self._pending_resolve
        for pnode, branches in branchmap.iteritems():
            branches = branchmap[pnode] = tuple(merge_propagate(diffitems,
                                                                branches))

            if not branches:
                raise PdagContextError
            if len(branches) == 1:
                resolved_pnodes.add(pnode)

        return

    def _diff_for(self, changeset):
        selfitems = set(self._dict.iteritems())

        # Contains _different_ pairs found in either dict, bot not in both.
        # This means that conflicting items are retained.
        diffitems = selfitems ^ changeset

        if len(dict(diffitems)) < len(diffitems):
            # There are some items with the same key, but different values.
            raise PdagContextError

        # Now diffitems holds only items that were not set in the self dict.
        diffitems -= selfitems

        return diffitems


