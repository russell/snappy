from setuptools import setup, find_packages
import sys, os

version = '0.0'

setup(name='snappy',
      version=version,
      description="Snap NLTK server side",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Russell Sim',
      author_email='russell.sim@gmail.com',
      url='',
      license='GPLv3',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'lxml',
          'nose',
          'twisted',
          'mock',
          'astor',
          'requests',
      ],
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      snappy-client = snappy.client:main
      """,
      )
