from setuptools import setup, find_packages
import sys, os, platform

version = '4.8.0'
requires = 'websockify'
if platform.machine() == 'sw_64':
    requires = 'websockify == 0.8.0'


setup(name='consoleproxy',
      version=version,
      description="zstack console proxy agent",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='zstack console proxy',
      author='Frank Zhang',
      author_email='xing5820@gmail.com',
      url='http://zstack.org',
      license='Apache License 2',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=True,
      install_requires=[
        requires,
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
