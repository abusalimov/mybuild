"""
Stuff for building namespace
"""

from mybuild._compat import *

class Namespace(object):
    """
    Backport of SimpleNamespace() class added in Python 3.3
    """
    def __init__(self, **kwargs):
        super(Namespace, self).__init__()
        self.__dict__.update(kwargs)

    def __iter__(self):
        return iter(self.__dict__)
    def __getitem__(self, key):
        return self.__dict__[key]
    def __setitem__(self, key, value):
        self.__dict__[key] = value
    def __delitem__(self, key):
        del self.__dict__[key]

    __hash__ = None
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))
