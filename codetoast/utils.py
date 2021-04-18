# -*- coding: utf-8 -*-

import pathlib
import typing
import pkg_resources


def package_version(package_name: str) -> typing.Optional[str]:

    try:
        return pkg_resources.get_distribution(package_name).version
    except (pkg_resources.DistributionNotFound, AttributeError):
        return None
