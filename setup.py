#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import with_statement

from setuptools import setup


with open('README.txt') as f:
    readme = f.read()

setup(
    name='ERPpeek',
    version='0.2',
    license='BSD',
    description='A tool for browsing OpenERP data from the command line',
    long_description=readme,
    url='https://code.launchpad.net/~openerp-community/openerp-tools/erppeek',
    author='Florent Xicluna',
    author_email='florent.xicluna@gmail.com',
    py_modules=['erppeek'],
    zip_safe=False,
    platforms='any',
    entry_points={
        'console_scripts': [
            'erppeek = erppeek:main',
        ]
    },
    keywords="openerp xml-rpc xmlrpc",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
