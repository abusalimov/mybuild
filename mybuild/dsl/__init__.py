"""
DSL loaders/bindings.
"""

__author__ = "Eldar Abusalimov"
__date__ = "2013-07-30"


from util.compat import *


def with_defaults(mapping, defaults_names, from_dict):
	ret_dict = dict(mapping) if mapping is not None else {}

	for name in defaults_names:
		ret_dict.setdefault(name, from_dict[name])

	return ret_dict


