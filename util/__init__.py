"""
Utils package.
"""


from _compat import *

import logging as _logging
import functools as _functools

from util.collections import is_container
from util.collections import is_mapping
import pprint


def identity(x):
    return x


logging_defaults = dict(
    level=_logging.DEBUG,
    filemode='w',
    format='%(levelname)-8s%(name)s:\t%(message)s',
)

def init_logging(filename_or_stream, **kwargs):
    init_dict = dict(logging_defaults, **kwargs)

    is_string = isinstance(filename_or_stream, basestring)
    init_dict['filename' if is_string else 'stream'] = filename_or_stream

    _logging.basicConfig(**init_dict)


def get_extended_logger(name):
	return extend_logger(_logging.getLogger(name))

def extend_logger(logger):
	logger.dump = _functools.partial(logger_dump, logger)
	logger.wrap = _functools.partial(logger_wrap, logger)
	return logger


def logger_wrap(logger, func, width=60):
    msg = ' {func.__name__} '.format(**locals())
    header = '---{msg:-<{width}}'.format(**locals())
    footer = '{msg:->{width}}---'.format(**locals())

    @_functools.wraps(func)
    def decorated(*args, **kwargs):
        logger.debug(header)
        try:
            return func(*args, **kwargs)
        finally:
            logger.debug(footer)

    return decorated


def logger_dump(logger, target, attrs=None):
    if not logger.isEnabledFor(_logging.DEBUG):
    	return

    if isinstance(attrs, str):
        attrs = attrs.split()
    if attrs is None:
        try:
            attrs = target._dump_attrs
        except AttributeError:
            attrs = filternot(invoker.startswith('_'), dir(target))

    logger.debug('%r', target)
    for attr in attrs:
        try:
            obj = getattr(target, attr)
        except AttributeError as e:
            obj = e
        else:
            obj = _log_dump_normalize(obj)

        try:
            obj_len = len(obj)
        except TypeError:
            msg = '.{0}:'.format(attr)
        else:
            msg = '.{0}: (len={1})'.format(attr, obj_len)

        logger.debug('\t||%s', msg)
        for line in pprint.pformat(obj).splitlines():
            logger.debug('\t||\t\t%s', line)


def _log_dump_normalize(obj):
    if is_mapping(obj):
        obj = dict((k, _log_dump_normalize(v)) for k, v in iteritems(obj))
    elif is_container(obj):
        obj = sorted(obj, key=repr)
    return obj

