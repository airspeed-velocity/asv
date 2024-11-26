# Licensed under a 3-clause BSD style license - see LICENSE.rst
import os
import itertools

from ..console import log
from ..publishing import OutputPublisher
from .. import util


def benchmark_param_iter(benchmark):
    """
    Iterate over all combinations of parameterized benchmark parameters.

    Yields
    ------
    idx : int
        Combination flat index. `None` if benchmark not parameterized.
    params : tuple
        Tuple of parameter values.

    """
    if not benchmark['params']:
        yield None, ()
    else:
        for item in enumerate(itertools.product(*benchmark['params'])):
            yield item

time_units = [
    ['`ps`', 'picoseconds', 0.000000000001],
    ['`ns`', 'nanoseconds', 0.000000001],
    ['`μs`', 'microseconds', 0.000001],
    ['`ms`', 'milliseconds', 0.001],
    ['`s`', 'seconds', 1],
    ['`m`', 'minutes', 60],
    ['`h`', 'hours', 60 * 60],
    ['`d`', 'days', 60 * 60 * 24],
    ['`w`', 'weeks', 60 * 60 * 24 * 7],
    ['`y`', 'years', 60 * 60 * 24 * 7 * 52],
    ['`C`', 'centuries', 60 * 60 * 24 * 7 * 52 * 100]
]

def pretty_time_unit(x, unit):
    if unit == 'seconds':
        for i in range(len(time_units) - 1):
            if abs(x) < time_units[i+1][2]:
                return '%.3f' % (x / time_units[i][2]) + time_units[i][0]
        return 'inf'
    else:
        return '%.3f' % x + unit

class ComparisonList(OutputPublisher):
    name = "comparisonlist"
    button_label = "List view"
    description = "Display as a list"
    order = 1

    @classmethod
    def publish(cls, conf, repo, benchmarks, graphs, revisions):
        machines = list(graphs.get_params()["machine"])
        num_machines = len(machines)
        baseline_machine_idx = -1
        if conf.baseline_machine:
            baseline_machine_idx = machines.index(conf.baseline_machine)

        result = {
            "machines" : machines,
            "benchmarks" : None,
        }
        benchmarks_result = []
        warned = False

        # Investigate all benchmarks
        for benchmark_name, benchmark in sorted(benchmarks.items()):
            log.dot()

            benchmark_graphs = graphs.get_graph_group(benchmark_name)

            # For parameterized benchmarks, consider each combination separately
            for idx, benchmark_param in benchmark_param_iter(benchmark):
                pretty_name = benchmark_name

                if benchmark.get('pretty_name'):
                    pretty_name = benchmark['pretty_name']

                if idx is not None:
                    pretty_name = '{0}({1})'.format(pretty_name,
                                                    ", ".join(benchmark_param))

                # Each environment parameter combination is reported
                # separately on the comparisonlist page
                benchmark_graphs = graphs.get_graph_group(benchmark_name)
                benchmark_data = None
                best_val = None
                worst_val = None
                for graph in benchmark_graphs:
                    machine_idx = machines.index(graph.params["machine"])
                    if not benchmark_data:
                        benchmark_data = {
                            "name" : benchmark_name,
                            "pretty_name" : pretty_name,
                            "idx" : idx,
                            "best" : -1,
                            "worst" : -1,
                            "last_rev" : [None] * num_machines,
                            "last_value" : [None] * num_machines,
                            "last_err" : [None] * num_machines,
                            "cmp_percent" : [0.] * num_machines,
                        }
                        
                    # Produce interesting information, based on
                    # stepwise fit on the benchmark data (reduces noise)
                    steps = graph.get_steps()
                    if idx is not None and steps:
                        steps = graph.get_steps()[idx]

                    last_value = None
                    last_err = None
                    last_rev = None

                    if not steps:
                        # No data
                        pass
                    else:
                        last_piece = steps[-1]
                        last_value = last_piece[2]
                        if best_val is None or last_value < best_val:
                            benchmark_data["best"] = machine_idx
                            best_val = last_value
                        if worst_val is None or last_value > worst_val:
                            benchmark_data["worst"] = machine_idx
                            worst_val = last_value
                        last_err = last_piece[4]
                        last_rev = last_piece[1] - 1
                        if not warned and benchmark_data["last_value"][machine_idx]:
                            warned = True
                            log.warning("There are two machines that has the same name '%s'" % machines[machine_idx])
                        benchmark_data["last_value"][machine_idx] = last_value
                        benchmark_data["last_err"][machine_idx] = last_err
                        benchmark_data["last_rev"][machine_idx] = last_rev
                if benchmark_data and best_val:
                    benchmarks_result.append(benchmark_data)

        if baseline_machine_idx != -1:
            num_benchmarks = len(benchmarks_result)
            cmp_list = [0.] * num_machines
            for bench_idx in range(num_benchmarks):
                values = benchmarks_result[bench_idx]["last_value"]
                b = values[baseline_machine_idx]
                if b:
                    for machine_idx in range(num_machines):
                        v = values[machine_idx]
                        if v:
                            p = (v - b) / b * 100
                            cmp_list[machine_idx] += p
                            benchmarks_result[bench_idx]["cmp_percent"][machine_idx] = p

            benchmarks_average_cmp = [None] * num_machines
            for machine_idx in range(num_machines):
                benchmarks_average_cmp[machine_idx] = cmp_list[machine_idx]/num_benchmarks
            result["average"] = benchmarks_average_cmp
            result["baseline"] = baseline_machine_idx
                

        def machine_idx_sort(row):
            idx = row['best']
            if idx == -1:
                return 9999
            if baseline_machine_idx != -1:
                if idx == baseline_machine_idx:
                    v = max(row["cmp_percent"])/100
                    return idx - v
                else:
                    v = row["cmp_percent"][idx]/100
                    return idx + v

            return idx
        result["benchmarks"] = sorted(benchmarks_result, key=machine_idx_sort)
        # Write results to file
        util.write_json(os.path.join(conf.html_dir, "comparison.json"), result, compact=True)

        if conf.generate_markdown:
            # Generate a markdown page
            with open(os.path.join(conf.html_dir, "comparison.md"), "w") as fp:
                machines = result["machines"]
                num_machines = len(machines)
                fp.write('# Benchmark Machine\n')
                fp.write('* CPU: %s\n' % list(graphs.get_params()["cpu"])[0])
                fp.write('* CPU Cores: %s\n' % list(graphs.get_params()["num_cpu"])[0])
                fp.write('* OS: %s\n' % list(graphs.get_params()["os"])[0])
                fp.write('* RAM: %dGB\n' % (int(list(graphs.get_params()["ram"])[0])//1000000))
                fp.write('\n\n')
                fp.write('# Results\n')
                fp.write('| No. |' + '|'.join(machines + ["Benchmarks"]) + '|\n')
                fp.write('| :-- |' + '|'.join([":--"] * (num_machines + 1)) + '|\n')
                if baseline_machine_idx != -1:
                    avg = ['%.2f%%' % v for v in result["average"]]
                    fp.write('| - |' + '|'.join(avg + ["Average"]) + '|\n')
                count = 1
                for benchmark in result["benchmarks"]:
                    if None in benchmark["last_value"]:
                        continue
                    unit = benchmarks[benchmark["name"]]["unit"]
                    row = '| %d ' % count
                    count += 1
                    for machine_idx in range(num_machines):
                        row += '|' + pretty_time_unit(benchmark["last_value"][machine_idx], unit)
                        if baseline_machine_idx != -1 and baseline_machine_idx != machine_idx:
                            row += ' `%.2f%%`' % benchmark["cmp_percent"][machine_idx]
                    row += '|' + benchmark["pretty_name"] + '|\n'
                    fp.write(row)
