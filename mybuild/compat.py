"""
2to3 compat stuff.
"""

import operator as _operator
import sys as _sys
_py3k = (_sys.version_info[0] == 3)


if _py3k:
    range  = range
    filter = filter
    map    = map
    zip    = zip
    next   = next

else:
    range = xrange
    from itertools import ifilter as filter
    from itertools import imap    as map
    from itertools import izip    as zip
    next = _operator.methodcaller('next')


if _py3k:
    itervalues = lambda d: iter(d.values())
    iteritems  = lambda d: iter(d.items())

else:
    itervalues = _operator.methodcaller('itervalues')
    iteritems  = _operator.methodcaller('iteritems')

iterkeys = iter


del _operator
del _sys
del _py3k
