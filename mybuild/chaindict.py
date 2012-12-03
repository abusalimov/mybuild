"""
Dictionary which supports chaining.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2012-11-30"

__all__ = ["ChainDict"]


class ChainDict(dict):
    """
    Delegates lookup for a missing key to the parent dictionary.
    """
    __slots__ = 'base' # a mapping (possibly with a 'base' too), or None

    def __init__(self, base=None, initial={}):
        dict.__init__(self, initial)
        self.base = base

    def __missing__(self, key):
        """Looks up the chain of ancestors for the key."""

        ancestor = self.base
        while ancestor is not None:
            if key in ancestor:
                # Found an ancestor which is suitable to handle the request.
                break

            try:
                ancestor = ancestor.base
            except AttributeError:
                # The the root dict may be a special one, like defaultdict.
                # Give the last chance to it, or let it raise error
                # independently.
                break
        else:
            raise KeyError

        return ancestor[key]

    def new_branch(self):
        cls = type(self)
        return cls(base=self)

    def iter_base_chain(self):
        ancestor = self.base

        while ancestor is not None:
            current = ancestor
            ancestor = getattr(ancestor, 'base', None)

            yield current

    def __repr__(self):
        return (dict.__repr__(self) if self.base is None else
                '%r <- %s' % (self.base, dict.__repr__(self)))


