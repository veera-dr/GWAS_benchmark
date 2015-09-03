"""
file to set up python package, see http://docs.python.org/2/distutils/setupscript.html for details.
"""


import platform
import os
import sys
import shutil
from setuptools import setup, Extension 
import numpy

# Version number
version = '0.1.3'


def readme():
    with open('README.md') as f:
       return f.read()

#python setup.py sdist bdist_wininst upload
setup(
    name='GWAS_benchmark',
    version=version,
    description='GWAS benchmark',
    long_description=readme(),
    keywords='gwas bioinformatics benchmarks',
    url="http://research.microsoft.com/en-us/um/redmond/projects/mscompbio/",
    author='MSR',
    author_email='fastlmm@microsoft.com',
    license='Apache 2.0',
    packages=[
        "GWAS_benchmark/tests",
        "GWAS_benchmark",
	],
    install_requires = ['scipy>=0.15.1', 'numpy>=1.9.2', 'pandas>=0.16.2', 'matplotlib>=1.4.3', 'scikit-learn>=0.16.1', 'pysnptools>=0.3.2', 'fastlmm>=0.2.17', 'fastcluster'],
  )

