# SPDX-License-Identifier: BSD-3-Clause

from importlib_metadata import version as get_version

from asv import plugin_manager  # noqa: F401 Needed to load the plugins

__version__ = get_version("asv")

__all__ = ('__version__',)
