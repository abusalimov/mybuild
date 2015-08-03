#!/usr/bin/env python
import setuptools
import sys


def have_arg(*args):
    return any(arg in sys.argv for arg in args)


def dict_of(cls):
    """Decorator that converts a class into a dict of its public members."""
    return {k: v for k, v in cls.__dict__.items() if not k.startswith('_')}


@dict_of
class setup_params:
    name = 'mybuild'
    version = '0.1'

    description = 'Build automation tool for modular applications'
    url = 'https://github.com/embox/mybuild'

    author = 'Eldar Abusalimov'
    author_email = 'eldar.abusalimov@gmail.com'

    license = 'MIT'

    classifiers = [
        'Private :: Do Not Upload',

        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ]
    keywords = 'mybuild build automation development tools'

    packages = setuptools.find_packages(include=['mybuild', 'mybuild.*'])

    install_requires = [
        'ply>=3.4',
    ]

    setup_requires = []
    if have_arg('pytest', 'test', 'ptr'):
        setup_requires += ['pytest_runner']

    @dict_of
    class extras_require:
        test = [
            'pytest',
        ]

        dev = test + [
            'pytest-catchlog',
            'pytest-cov',
        ]

    tests_require = extras_require['test']


if __name__ == '__main__':
    # Guarded to make the module importable by tools like pytest.
    setuptools.setup(**setup_params)
