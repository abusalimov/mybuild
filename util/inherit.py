"""
Dynamic inheritance for class members.
"""

from _compat import *


class InheritMetaBase(type):
    pass

class InheritOwnerMeta(InheritMetaBase):
    pass

class InheritValueMeta(InheritMetaBase):
    pass

