"""Build automation tool for modular and configurable applications.

As many other build systems, Mybuild requires some metadata to be described in
special separate files that usually reside in same directories as the
application source files files. These files are written in a custom declarative
DSL (domain-specific language) and contain definitions of build units, their
configuration options, dependencies and requirements. Based on a given
configuration these requirements are then resolved, that is satisfying
dependencies and inferring values for missing configuration options.

This works in a pretty much similar way like package managers do: when a user
asks to install a package, it is installed among with the necessary packages it
depends on. If it is not possible to satisfy the request, an error is reported,
explaining the reasons of the conflict.

Here is a high-level overview of sub-packages of the `mybuild` package:

  * `mybuild.core`: Defines basic model types for module, options, etc. Given a
    root configuration, discovers any directly or indirectly referenced modules
    and prepares a pgraph for the solver.

  * `mybuild.req`: A generic boolean formula solver as a requirement satisfying
    engine. It is used to figure out option values, resolve module
    dependencies, check for conflicts etc. It is also able to explain the
    solution.

  * `mybuild.lang`: A support for the declarative DSL. Translates the input
    files and interprets them as a Python code.

  * `mybuild.nsimporter`: Hooks into the Python import mechanism to provide
    easy and native integration with the declarative DSL.
"""

# Compatibility notes.
#
# All modules should be written primarily for Python 3 with basic Python 2.7
# compatibility kept in mind (but not at a cost of code readability or
# maintainability!). For more information please refer to the `mybuild._compat`
# module.
#
# In a nutshell, ALWAYS import the following at the top of all modules.
from __future__ import absolute_import, division, print_function
from mybuild._compat import *


__author__ = "Eldar Abusalimov"
__copyright__ = "Copyright 2012-2015, Eldar Abusalimov"
__license__ = "MIT"
__version__ = "0.5"

