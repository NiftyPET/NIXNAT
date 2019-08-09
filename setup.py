#!/usr/bin/env python
""" XNAT input/output functionalities for namespace package 'niftypet'.
"""
__author__      = "Pawel J. Markiewicz"
__copyright__   = "Copyright 2019"
# ---------------------------------------------------------------------------------

from setuptools import setup, find_packages

import os
import sys
import platform


#===============================================================
# PYTHON SETUP
#===============================================================

print('i> found those packages:')
print(find_packages(exclude=['docs']))

with open('README.rst') as file:
    long_description = file.read()


#----------------------------
setup(
    name='nixnat',
    license = 'Apache 2.0',
    version='0.1.0',
    description='XNAT input/output.',
    long_description=long_description,
    author='Pawel J. Markiewicz',
    author_email='p.markiewicz@ucl.ac.uk',
    url='https://github.com/pjmark/NiftyPET',
    keywords='XNAT input output',
    install_requires=['pydicom'],
    packages=find_packages(exclude=['docs']),
    zip_safe=False,
)
#===============================================================
