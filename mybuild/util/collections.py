from __future__ import absolute_import, division, print_function
from mybuild._compat import *

from collections import *

from mybuild.util.operator import instanceof


is_mapping   = instanceof(Mapping)
is_container = instanceof(Container)
is_sized     = instanceof(Sized)
is_sequence  = instanceof(Sequence)
is_set       = instanceof(Set)
