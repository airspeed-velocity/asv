#!/usr/bin/env python3

from pathlib import Path
import itertools
import math

import tabulate
from asv_runner.console import color_print
from asv_runner.statistics import get_err

from asv import results
from asv.console import log
from asv.util import human_value, load_json
from asv import _stats
from asv.commands.compare import _is_result_better, unroll_result, _isna

import asv
import click


@click.command()
@click.argument("b1", type=click.Path(exists=True), required=True)
@click.argument("b2", type=click.Path(exists=True), required=True)
@click.argument("bconf", type=click.Path(exists=True), required=True)
def comparer(b1, b2, bconf):
    click.echo(f"Hello, comparing {b1} and {b2}!")
    do_compare(b1, b2, bconf)


def result_iter(bdot):
    for key in bdot.get_all_result_keys():
        params = bdot.get_result_params(key)
        result_value = bdot.get_result_value(key, params)
        result_stats = bdot.get_result_stats(key, params)
        result_samples = bdot.get_result_samples(key, params)
        result_version = bdot.benchmark_version.get(key)
        yield (
            key,
            params,
            result_value,
            result_stats,
            result_samples,
            result_version,
            bdot.params["machine"],
            bdot.env_name,
        )


def do_compare(
    b1,
    b2,
    bconf,
    factor=1.1,
    split=False,
    only_changed=False,
    sort="default",
    machine=None,
    env_spec=None,
    use_stats=True,
):
    # Already validated by click normally
    res_1 = results.Results.load(b1)
    res_2 = results.Results.load(b2)
    conf_asv = asv.config.Config()
    conf_asv.results_dir = Path(bconf).parent
    benchmarks = asv.benchmarks.Benchmarks.load(conf_asv)
    # Kanged from compare.py

    results_1 = {}
    results_2 = {}
    ss_1 = {}
    ss_2 = {}
    versions_1 = {}
    versions_2 = {}
    units = {}

    machine_env_names = set()

    for key, params, value, stats, samples, version, machine, env_name in result_iter(
        res_1
    ):
        machine_env_name = f"{machine}/{env_name}"
        machine_env_names.add(machine_env_name)
        for name, value, stats, samples in unroll_result(
            key, params, value, stats, samples
        ):
            units[name] = benchmarks.get(key, {}).get("unit")
            results_1[name] = value
            ss_1[name] = (stats, samples)
            versions_1[name] = version

    for key, params, value, stats, samples, version, machine, env_name in result_iter(
        res_2
    ):
        machine_env_name = f"{machine}/{env_name}"
        machine_env_names.add(machine_env_name)
        for name, value, stats, samples in unroll_result(
            key, params, value, stats, samples
        ):
            units[name] = benchmarks.get(key, {}).get("unit")
            results_2[name] = value
            ss_2[name] = (stats, samples)
            versions_2[name] = version

    benchmarks_1 = set(results_1.keys())
    benchmarks_2 = set(results_2.keys())
    joint_benchmarks = sorted(list(benchmarks_1 | benchmarks_2))
    bench = {}

    if split:
        bench["green"] = []
        bench["red"] = []
        bench["lightgrey"] = []
        bench["default"] = []
    else:
        bench["all"] = []

    worsened = False
    improved = False

    for benchmark in joint_benchmarks:
        if benchmark in results_1:
            time_1 = results_1[benchmark]
        else:
            time_1 = math.nan

        if benchmark in results_2:
            time_2 = results_2[benchmark]
        else:
            time_2 = math.nan

        if benchmark in ss_1 and ss_1[benchmark][0]:
            err_1 = get_err(time_1, ss_1[benchmark][0])
        else:
            err_1 = None

        if benchmark in ss_2 and ss_2[benchmark][0]:
            err_2 = get_err(time_2, ss_2[benchmark][0])
        else:
            err_2 = None

        version_1 = versions_1.get(benchmark)
        version_2 = versions_2.get(benchmark)

        if _isna(time_1) or _isna(time_2):
            ratio = "n/a"
            ratio_num = 1e9
        else:
            try:
                ratio_num = time_2 / time_1
                ratio = f"{ratio_num:6.2f}"
            except ZeroDivisionError:
                ratio_num = 1e9
                ratio = "n/a"

        if version_1 is not None and version_2 is not None and version_1 != version_2:
            # not comparable
            color = "lightgrey"
            mark = "x"
        elif time_1 is not None and time_2 is None:
            # introduced a failure
            color = "red"
            mark = "!"
            worsened = True
        elif time_1 is None and time_2 is not None:
            # fixed a failure
            color = "green"
            mark = " "
            improved = True
        elif time_1 is None and time_2 is None:
            # both failed
            color = "default"
            mark = " "
        elif _isna(time_1) or _isna(time_2):
            # either one was skipped
            color = "default"
            mark = " "
        elif _is_result_better(
            time_2,
            time_1,
            ss_2.get(benchmark),
            ss_1.get(benchmark),
            factor,
            use_stats=use_stats,
        ):
            color = "green"
            mark = "-"
            improved = True
        elif _is_result_better(
            time_1,
            time_2,
            ss_1.get(benchmark),
            ss_2.get(benchmark),
            factor,
            use_stats=use_stats,
        ):
            color = "red"
            mark = "+"
            worsened = True
        else:
            color = "default"
            mark = " "

            # Mark statistically insignificant results
            if _is_result_better(
                time_1, time_2, None, None, factor
            ) or _is_result_better(time_2, time_1, None, None, factor):
                ratio = "~" + ratio.strip()

        if only_changed and mark in (" ", "x"):
            continue

        unit = units[benchmark]

        details = "{0:1s} {1:>15s}  {2:>15s} {3:>8s}  ".format(
            mark,
            human_value(time_1, unit, err=err_1),
            human_value(time_2, unit, err=err_2),
            ratio,
        )
        split_line = details.split()
        if len(machine_env_names) > 1:
            benchmark_name = "{} [{}]".format(*benchmark)
        else:
            benchmark_name = benchmark[0]
        if len(split_line) == 4:
            split_line += [benchmark_name]
        else:
            split_line = [" "] + split_line + [benchmark_name]
        if split:
            bench[color].append(split_line)
        else:
            bench["all"].append(split_line)

    if split:
        keys = ["green", "default", "red", "lightgrey"]
    else:
        keys = ["all"]

    titles = {}
    titles["green"] = "Benchmarks that have improved:"
    titles["default"] = "Benchmarks that have stayed the same:"
    titles["red"] = "Benchmarks that have got worse:"
    titles["lightgrey"] = "Benchmarks that are not comparable:"
    titles["all"] = "All benchmarks:"

    log.flush()

    for key in keys:

        if len(bench[key]) == 0:
            continue

        if not only_changed:
            color_print("")
            color_print(titles[key])
            color_print("")

        name_1 = False  # commit_names.get(hash_1)
        if name_1:
            name_1 = f"<{name_1}>"
        else:
            name_1 = ""

        name_2 = False  # commit_names.get(hash_2)
        if name_2:
            name_2 = f"<{name_2}>"
        else:
            name_2 = ""

        if sort == "default":
            pass
        elif sort == "ratio":
            bench[key].sort(key=lambda v: v[3], reverse=True)
        elif sort == "name":
            bench[key].sort(key=lambda v: v[2])
        else:
            raise ValueError("Unknown 'sort'")

        print(
            tabulate.tabulate(
                bench[key],
                headers=[
                    "Change",
                    f"Before {name_1}",
                    f"After {name_2}",
                    "Ratio",
                    "Benchmark (Parameter)",
                ],
                tablefmt="github",
            )
        )


if __name__ == "__main__":
    comparer()
