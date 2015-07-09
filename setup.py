from setuptools import setup, find_packages

def subpackage_globs(*names):
    return [prefix + name + suffix for name in names
            for prefix in ('', '*.')
            for suffix in ('', '.*')]

setup(
    name='mybuild',
    version='0.5',

    description='Build automation tool for modular applications',
    url='https://github.com/embox/mybuild',

    author='Eldar Abusalimov',
    author_email='eldar.abusalimov@gmail.com',

    license='BSD',

    classifiers=[
        'Private :: Do Not Upload',

        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: BSD License',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='mybuild build automation development tools',

    packages=find_packages(exclude=(subpackage_globs('test', 'tests') +
                                    ['example', 'sublime-plugin'])),

    install_requires=['ply>=3.6'],
)
