# SPDX-License-Identifier: BSD-3-Clause

import math


class OutputPublisher:
    """
    A base class for pages displaying output in the JS application
    """

    name = None
    button_label = None
    description = None
    order = math.inf

    @classmethod
    def publish(cls, conf, repo, benchmarks, graphs, revisions):
        pass
