# SPDX-License-Identifier: BSD-3-Clause

from ..console import log
from ..publishing import OutputPublisher


class SummaryGrid(OutputPublisher):
    name = ""
    button_label = "Grid view"
    description = "Display as a agrid"
    order = 0

    @classmethod
    def publish(cls, conf, repo, benchmarks, graphs, revisions):
        # Generate and save summary graphs
        summaries = graphs.get_summary_graphs(dots=log.dot)
        for graph in summaries:
            graph.save(conf.html_dir)
