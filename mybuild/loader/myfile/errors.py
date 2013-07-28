"""
Scoping and linking logic.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-28"


from ...util.compat import *


class LinkageError(Exception):
    pass

class CompoundError(LinkageError):
    def __init__(self, *causes):
        super(CompoundError, self).__init__('\n'.join(map(str, causes)))

class UnresolvedNameError(LinkageError, NameError):
    pass

class UnresolvedAttributeError(LinkageError, AttributeError):
    pass

class ReferenceLoopError(LinkageError, TypeError):
    def __init__(self, chain_ex):
        chain = reversed(chain_ex.chain)
        chain_tree = '\n'.join('%s -> %s' % (' ' * (depth * 4), obj)
                               for depth, obj in enumerate(chain))
        super(ReferenceLoopError, self).__init__(
                "%s object references itself (eventually)\n%s" %
                (chain_ex.chain_init, chain_tree))


