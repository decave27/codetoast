# -*- coding: utf-8 -*-

from collections import namedtuple

__all__ = (
    '__author__',
    '__copyright__',
    '__docformat__',
    '__license__',
    '__title__',
    '__version__',
    'version_info'
)

VersionInfo = namedtuple('VersionInfo', 'major minor micro releaselevel serial')
version_info = VersionInfo(major=2, minor=0, micro=0, releaselevel='final', serial=0)

__author__ = 'decave27'
__copyright__ = 'Copyright 2021 Decave (jishaku Gorialis, Devon)'
__docformat__ = 'restructuredtext en'
__license__ = 'MIT'
__title__ = 'decave27'
__version__ = '.'.join(map(str, (version_info.major, version_info.minor, version_info.micro)))