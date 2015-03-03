# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, unicode_literals, print_function

import os

from ..console import log
from ..publishing import OutputPublisher
from ..step_detect import detect_regressions

from .. import util


#
# Generating output
#


class Regressions(OutputPublisher):
    name = "regressions"
    button_label = "Regression detection"
    description = "Display information about recent regressions"

    @classmethod
    def publish(cls, conf, graphs):
        cls._save(conf, {})

    @classmethod
    def _save(cls, conf, data):
        fn = os.path.join(conf.html_dir, 'regressions.json')
        util.write_json(fn, data)
