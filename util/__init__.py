"""
Utils package.
"""

import logging as _logging
from util.compat import *


def identity(x):
    return x


logging_defaults = dict(
    level=_logging.DEBUG,
    filemode='w',
    format='%(levelname)-8s%(name)s:\t%(message)s',
)

def init_logging(filename, **kwargs):
    _logging.basicConfig(**dict(logging_defaults, filename=filename, **kwargs))

