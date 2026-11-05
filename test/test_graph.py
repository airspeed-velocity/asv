# Licensed under a 3-clause BSD style license - see LICENSE.rst

import os

from asv import util
from asv.graph import (
    RESAMPLED_POINTS,
    Graph,
    _combine_graph_data,
    _fill_missing_data,
    make_summary_graph,
)
from asv.step_detect import detect_regressions


def test_graph_single():
    vals = [
        (1, 1, None),
        (2, 2, 1),
        (3, 3, None),
        (4, 4, 7),
        (5, 5, None),
        (6, None, None),
        (7, float('nan'), None),
    ]

    # Should give same data back, excluding missing values at edges
    g = Graph('foo', {})
    for k, v, dv in vals:
        g.add_data_point(k, v, dv)
    data = g.get_data()
    assert data == vals[:-2]

    # Should average duplicate values
    g = Graph('foo', {})
    g.add_data_point(4, 3)
    for k, v, dv in vals:
        g.add_data_point(k, v, dv)
    g.add_data_point(4, 5)
    data = g.get_data()
    assert data[3][0] == 4
    assert abs(data[3][1] - (3 + 4 + 5) / 3.0) < 1e-10

    # Summary graph should be the same as the main graph
    g = Graph('foo', {})
    for k, v, dv in vals:
        g.add_data_point(k, v, dv)
    g = make_summary_graph([g])
    data = g.get_data()
    assert len(data) == len(vals) - 2
    for v, d in zip(vals, data):
        kv, xv, dv = v
        kd, xd, dd = d
        assert kv == kd
        assert dd is None
        assert abs(xv - xd) < 1e-10


def test_graph_multi():
    vals = [
        (0, [None, None, None], [None] * 3),
        (1, [1, None, float('nan')], [None] * 3),
        (2, [2, 5, 4], [1] * 3),
        (3, [3, 4, -60], [None] * 3),
        (4, [4, 3, 2], [None] * 3),
        (5, [None, 2, None], [None] * 3),
        (6, [6, 1, None], [None] * 3),
    ]

    # Revision 5 interpolates the one-point hole in series 0 (4 then 6 -> 5).
    # Series 2 has no later sample, so its last value is carried forward.
    filled_vals = [
        (1, [1, None, None]),
        (2, [2, 5, 4]),
        (3, [3, 4, -60]),
        (4, [4, 3, 2]),
        (5, [5, 2, 2]),
        (6, [6, 1, 2]),
    ]

    # Should give same data back, with missing data at edges removed
    g = Graph('foo', {})
    for k, v, dv in vals:
        g.add_data_point(k, v, dv)
    data = g.get_data()
    assert data[0] == (1, [1, None, None], [None, None, None])
    assert data[1:] == vals[2:]

    # Should average duplicate values
    g = Graph('foo', {})
    g.add_data_point(4, [1, 2, 3])
    for k, v, dv in vals:
        g.add_data_point(k, v, dv)
    g.add_data_point(4, [3, 2, 1])
    data = g.get_data()
    assert data[3][0] == 4
    assert abs(data[3][1][0] - (1 + 4 + 3) / 3.0) < 1e-10
    assert abs(data[3][1][1] - (2 + 3 + 2) / 3.0) < 1e-10
    assert abs(data[3][1][2] - (3 + 2 + 1) / 3.0) < 1e-10

    # The summary graph is the geometric mean after filling missing data
    g = Graph('foo', {})
    for k, v, dv in vals:
        g.add_data_point(k, v, dv)
    g = make_summary_graph([g])
    data = g.get_data()

    for v, d in zip(filled_vals, data):
        kv, xvs = v
        kd, xd, dd = d
        assert kv == kd

        # geom mean, with some sign convention
        expected = util.geom_mean_na(xvs)
        assert (xd is None and expected is None) or abs(xd - expected) < 1e-10

    # Test summary over separate graphs -- should behave as if the
    # data was in a single graph
    g0 = Graph('foo', {})
    g1 = Graph('foo', {})
    g2 = Graph('foo', {})
    for k, v, dv in vals:
        g0.add_data_point(k, v, dv)
        g1.add_data_point(k, v[0], dv[0])
        g2.add_data_point(k, v[1:], dv[1:])

    data0 = make_summary_graph([g0]).get_data()
    data = make_summary_graph([g1, g2]).get_data()
    assert data == data0

    # Check the above is true regardless if some x-values are missing
    g0.add_data_point(7, [None, 1, None])
    g2.add_data_point(7, [1, None])

    g0.add_data_point(4.5, [9, None, None])
    g1.add_data_point(4.5, 9)

    data0 = make_summary_graph([g0]).get_data()
    data = make_summary_graph([g1, g2]).get_data()
    assert data == data0


def test_empty_graph():
    g = Graph('foo', {})
    g.add_data_point(1, None)
    g.add_data_point(2, None)
    g.add_data_point(3, None)
    data = g.get_data()
    assert data == []

    g = Graph('foo', {})
    g.add_data_point(1, None)
    g.add_data_point(1, [None, None])
    g.add_data_point(2, [None, None])
    g.add_data_point(3, None)
    g.add_data_point(4, [None, None])
    data = g.get_data()
    assert data == []


def test_nan():
    g = Graph('foo', {})
    g.add_data_point(1, 1)
    g.add_data_point(2, 2)
    g.add_data_point(2, float('nan'))
    g.add_data_point(3, 3)
    g.add_data_point(4, float('nan'))
    data = g.get_data()
    assert data == [(1, 1, None), (2, 2, None), (3, 3, None)]

    g = Graph('foo', {})
    g.add_data_point(1, None)
    g.add_data_point(1, [1, float('nan')])
    g.add_data_point(2, [2, 2])
    g.add_data_point(3, [float('nan'), float('nan')])
    g.add_data_point(4, [None, float('nan')])
    data = g.get_data()
    assert data == [(1, [1, None], [None, None]), (2, [2, 2], [None, None])]


def test_summary_graph():
    n = 2 * int(RESAMPLED_POINTS)
    g = Graph('foo', {})
    for i in range(n):
        g.add_data_point(i, 0.1)
        g.add_data_point(n + i, 0.2)
    g = make_summary_graph([g])
    data = g.get_data()
    assert len(data) == 512
    for i in range(256):
        assert abs(data[i][1] - 0.1) < 1e-7
        assert abs(data[256 + i][1] - 0.2) < 1e-7


def test_summary_graph_loop():
    n = int(RESAMPLED_POINTS)

    # Resampling shouldn't get stuck in an infinite loop
    g = Graph('foo', {})
    for j in range(n):
        g.add_data_point(j, 0.1)
    g = make_summary_graph([g])
    data = g.get_data()
    assert len(data) == 1
    assert data[0][0] == n
    assert abs(data[0][1] - 0.1) < 1e-7


def test__fill_missing_data():
    y = [None, 1, 2, None, None, 5, None, 7, None]
    filled = _fill_missing_data(y, max_gap_fraction=0.5)
    assert filled == [None, 1, 2, 3, 4, 5, 6, 7, None]

    filled = _fill_missing_data(y, max_gap_fraction=0.1)
    assert filled == [None, 1, 2, None, None, 5, 6, 7, None]


def _summary_values(graphs):
    data = make_summary_graph(graphs).get_data()
    return [(row[0], row[1]) for row in data]


def _assert_summary(graphs, expected):
    summary = _summary_values(graphs)
    assert [rev for rev, _val in summary] == [rev for rev, _val in expected]
    for (_rev, got), (_expected_rev, want) in zip(summary, expected):
        assert abs(got - want) < 1e-12


def _machine(name, points, branch=None):
    params = {'machine': name}
    if branch is not None:
        params['branch'] = branch
    graph = Graph('time_func', params)
    for rev, value in points:
        graph.add_data_point(rev, value)
    return graph


def test_summary_missing_machines_keep_level():
    # Three machines, constant timings. blue misses four commits and red
    # misses two. The landing-page summary must stay at the full-set mean.
    slow, mid, fast = 4.0, 2.0, 1.0
    expected = util.geom_mean_na([slow, mid, fast])
    present = {'blue': [0, 1], 'red': [0, 1, 2, 3], 'purple': list(range(6))}
    values = {'blue': slow, 'red': mid, 'purple': fast}
    graphs = []
    for name, commits in present.items():
        graph = Graph('time_func', {'machine': name})
        for rev in commits:
            graph.add_data_point(rev, values[name])
        graphs.append(graph)

    summary = _summary_values(graphs)
    assert [rev for rev, _val in summary] == [0, 1, 2, 3, 4, 5]
    for _rev, val in summary:
        assert abs(val - expected) < 1e-12

    # The per-machine series itself is not filled in. Missing commits stay absent.
    blue = graphs[0].get_data()
    assert [row[0] for row in blue] == [0, 1]
    assert [row[1] for row in blue] == [4.0, 4.0]


def test_summary_large_interior_gap_carries_last_value():
    # valid_count is 7, so the interpolator only fills a gap of 1.
    # A four-commit hole must keep the previous measurement, not drop the series.
    slow = Graph('time_func', {'machine': 'slow'})
    fast = Graph('time_func', {'machine': 'fast'})
    for rev in range(11):
        fast.add_data_point(rev, 1.0)
        if rev < 3 or rev > 6:
            slow.add_data_point(rev, 4.0)
    expected = util.geom_mean_na([4.0, 1.0])
    summary = _summary_values([slow, fast])
    assert [rev for rev, _val in summary] == list(range(11))
    for _rev, val in summary:
        assert abs(val - expected) < 1e-12


def test_summary_uses_new_value_when_series_returns():
    slow = Graph('time_func', {'machine': 'slow'})
    fast = Graph('time_func', {'machine': 'fast'})
    slow.add_data_point(0, 4.0)
    slow.add_data_point(1, 4.0)
    slow.add_data_point(4, 8.0)
    for rev in range(5):
        fast.add_data_point(rev, 1.0)
    held = util.geom_mean_na([4.0, 1.0])
    jumped = util.geom_mean_na([8.0, 1.0])
    summary = _summary_values([slow, fast])
    assert [rev for rev, _val in summary] == [0, 1, 2, 3, 4]
    for rev in (0, 1, 2, 3):
        assert abs(summary[rev][1] - held) < 1e-12
    assert abs(summary[4][1] - jumped) < 1e-12


def test_summary_does_not_invent_values_before_first_sample():
    late = Graph('time_func', {'machine': 'late'})
    early = Graph('time_func', {'machine': 'early'})
    for rev in range(4):
        early.add_data_point(rev, 1.0)
    late.add_data_point(2, 4.0)
    late.add_data_point(3, 4.0)
    summary = _summary_values([late, early])
    joined = util.geom_mean_na([4.0, 1.0])
    assert [rev for rev, _val in summary] == [0, 1, 2, 3]
    assert abs(summary[0][1] - 1.0) < 1e-12
    assert abs(summary[1][1] - 1.0) < 1e-12
    assert abs(summary[2][1] - joined) < 1e-12
    assert abs(summary[3][1] - joined) < 1e-12


def test_summary_parameter_gap_carries_that_series_only():
    # Two parameters share a machine. The second misses two commits, with a
    # failed sample and a NaN sample, then returns at a new value.
    both = Graph('time_func', {'machine': 'blue'})
    both.add_data_point(0, [4.0, 1.0])
    both.add_data_point(1, [4.0, None])
    both.add_data_point(2, [4.0, float('nan')])
    both.add_data_point(3, [8.0, 2.0])
    held = util.geom_mean_na([4.0, 1.0])
    jumped = util.geom_mean_na([8.0, 2.0])
    _assert_summary([both], [(0, held), (1, held), (2, held), (3, jumped)])

    # The second parameter has no sample yet, so those commits use the first.
    late = Graph('time_func', {'machine': 'blue'})
    late.add_data_point(0, [4.0, None])
    late.add_data_point(1, [4.0, float('nan')])
    late.add_data_point(2, [4.0, 1.0])
    _assert_summary([late], [(0, 4.0), (1, 4.0), (2, held)])


def test_summary_branches_do_not_share_carried_values():
    # Date order interleaves main (0, 1, 3) and topic (0, 2, 4). blue stops
    # on main after revision 1. topic keeps its own line and must not inherit
    # main's last sample, including through the one-commit hole at revision 2.
    blue_main = _machine('blue', [(0, 4.0), (1, 4.0)], branch='main')
    purple_main = _machine('purple', [(0, 2.0), (1, 2.0), (3, 8.0)], branch='main')
    purple_topic = _machine('purple', [(0, 2.0), (2, 2.0), (4, 2.0)], branch='topic')
    early = util.geom_mean_na([4.0, 2.0])
    shared = util.geom_mean_na([4.0, 2.0, 2.0])
    main_jump = util.geom_mean_na([4.0, 8.0])
    _assert_summary(
        [blue_main, purple_main, purple_topic],
        [
            (0, shared),
            (1, early),
            (2, 2.0),
            (3, main_jump),
            (4, 2.0),
        ],
    )


def test_summary_side_branch_does_not_change_later_main():
    # Revision 2 exists only on feature. Later main commits must stay at
    # the main mean: the feature sample must not be repeated there.
    # The slow main machine still keeps its last sample on main.
    slow = Graph('time_func', {'machine': 'slow', 'branch': 'main'})
    fast = Graph('time_func', {'machine': 'fast', 'branch': 'main'})
    side = Graph('time_func', {'machine': 'fast', 'branch': 'feature'})
    slow.add_data_point(0, 4.0)
    slow.add_data_point(1, 4.0)
    for rev in (0, 1, 3, 4, 5):
        fast.add_data_point(rev, 1.0)
    side.add_data_point(2, 100.0)

    summary = _summary_values([slow, fast, side])
    assert [rev for rev, _val in summary] == [0, 1, 2, 3, 4, 5]
    held = util.geom_mean_na([4.0, 1.0])
    for rev in (0, 1, 3, 4, 5):
        assert abs(summary[rev][1] - held) < 1e-12
    assert abs(summary[2][1] - 100.0) < 1e-12


def test_summary_failed_commit_still_counts_in_gap():
    # Commit 6 failed on both machines, and A also missed commit 5. The
    # failed commit belongs to the branch, so A's hole is two commits long
    # and the interpolator gives 6.0 at commit 5, the same as before the
    # carry-forward. A second branch must not change that.
    for side in (False, True):
        main_revs = [rev for rev in range(14) if not (side and rev == 3)]
        a_main = _machine(
            'A',
            [(rev, 4.0 if rev <= 4 else 10.0) for rev in main_revs if rev not in (5, 6)],
            branch='main',
        )
        b_main = _machine('B', [(rev, 1.0) for rev in main_revs if rev != 6], branch='main')
        a_main.add_data_point(6, None)
        b_main.add_data_point(6, None)
        graphs = [a_main, b_main]
        if side:
            graphs.append(_machine('B', [(3, 1.0)], branch='feature'))
        summary = dict(_summary_values(graphs))
        assert summary[6] is None
        assert abs(summary[5] - util.geom_mean_na([6.0, 1.0])) < 1e-12
        assert abs(summary[7] - util.geom_mean_na([10.0, 1.0])) < 1e-12


def test_summary_failed_and_nan_samples_keep_last_finite_value():
    # Scalar failures and skips are not stored. The other machine holds the
    # revisions on the axis, and a long hole repeats the last finite time.
    failed = Graph('time_func', {'machine': 'blue'})
    failed.add_data_point(0, 4.0)
    failed.add_data_point(1, 4.0)
    failed.add_data_point(2, None)
    failed.add_data_point(3, float('nan'))
    failed.add_data_point(4, float('nan'))
    failed.add_data_point(5, None)
    failed.add_data_point(6, 8.0)
    other = Graph('time_func', {'machine': 'purple'})
    for rev in range(7):
        other.add_data_point(rev, 1.0)
    held = util.geom_mean_na([4.0, 1.0])
    jumped = util.geom_mean_na([8.0, 1.0])
    summary = _summary_values([failed, other])
    assert [rev for rev, _val in summary] == list(range(7))
    for rev in range(6):
        assert abs(summary[rev][1] - held) < 1e-12
    assert abs(summary[6][1] - jumped) < 1e-12

    # A single missing sample between two real ones stays on the interpolator.
    # The other parameter is present, so the commit is not an all-missing hole.
    for missing in (None, float('nan')):
        short = Graph('time_func', {'machine': 'blue'})
        short.add_data_point(0, [4.0, 1.0])
        short.add_data_point(1, [missing, 1.0])
        short.add_data_point(2, [10.0, 1.0])
        _assert_summary(
            [short],
            [
                (0, util.geom_mean_na([4.0, 1.0])),
                (1, util.geom_mean_na([7.0, 1.0])),
                (2, util.geom_mean_na([10.0, 1.0])),
            ],
        )


def test_summary_stopped_series_carries_to_end_without_changing_steps():
    # blue never runs again. The summary keeps blue's last time through the
    # last revision of this branch. Step detection still sees only real samples,
    # which is the series the regressions page reads.
    slow = _machine('slow', [(0, 4.0), (1, 4.0)], branch='main')
    fast = _machine(
        'fast',
        [(rev, 1.0) for rev in range(4)] + [(4, 2.0), (5, 2.0)],
        branch='main',
    )
    slow_steps = slow.get_steps()
    fast_steps = fast.get_steps()
    slow_data = slow.get_data()
    fast_data = fast.get_data()

    held = util.geom_mean_na([4.0, 1.0])
    jumped = util.geom_mean_na([4.0, 2.0])
    _assert_summary(
        [slow, fast],
        [(rev, held) for rev in range(4)] + [(4, jumped), (5, jumped)],
    )

    assert slow.get_data() == slow_data
    assert fast.get_data() == fast_data
    slow._steps = None
    fast._steps = None
    assert slow.get_steps() == slow_steps
    assert fast.get_steps() == fast_steps
    assert slow_steps[-1][1] == 2
    assert detect_regressions(slow_steps) == (None, None, None)
    last, best, jumps = detect_regressions(fast_steps)
    assert jumps
    assert abs(last - 2.0) < 1e-12
    assert abs(best - 1.0) < 1e-12


def test_summary_machine_that_never_ran_adds_nothing():
    purple = Graph('time_func', {'machine': 'purple'})
    for rev in range(4):
        purple.add_data_point(rev, 1.0)
    ghost = Graph('time_func', {'machine': 'ghost'})
    ghost.add_data_point(0, None)
    ghost.add_data_point(1, float('nan'))
    ghost.add_data_point(2, [None, float('nan')])
    ghost.add_data_point(3, [None, None])
    never = Graph('time_func', {'machine': 'never'})
    summary = _summary_values([purple, ghost, never])
    assert [rev for rev, _val in summary] == [0, 1, 2, 3]
    for _rev, val in summary:
        assert abs(val - 1.0) < 1e-12


def test_summary_all_series_missing_on_a_commit_stays_missing():
    # Every parameter is missing on the middle commit. The summary keeps
    # that revision and records no value there, rather than repeating 4.0.
    only = Graph('time_func', {'machine': 'only'})
    only.add_data_point(0, [2.0, 8.0])
    only.add_data_point(1, [None, float('nan')])
    only.add_data_point(2, [2.0, 8.0])
    summary = _summary_values([only])
    assert [rev for rev, _val in summary] == [0, 1, 2]
    assert abs(summary[0][1] - 4.0) < 1e-12
    assert summary[1][1] is None
    assert abs(summary[2][1] - 4.0) < 1e-12

    blue = Graph('time_func', {'machine': 'blue'})
    purple = Graph('time_func', {'machine': 'purple'})
    for rev in (0, 1, 3):
        blue.add_data_point(rev, 4.0)
        purple.add_data_point(rev, 1.0)
    summary = _summary_values([blue, purple])
    assert [rev for rev, _val in summary] == [0, 1, 3]
    expected = util.geom_mean_na([4.0, 1.0])
    for _rev, val in summary:
        assert abs(val - expected) < 1e-12


def test_summary_carry_follows_revision_number_order():
    # 8.0 is inserted first, on a later revision. Earlier gaps must keep 4.0.
    slow = _machine('slow', [(4, 8.0), (0, 4.0), (1, 4.0)])
    fast = _machine(
        'fast',
        [(5, 1.0), (2, 1.0), (0, 1.0), (4, 1.0), (1, 1.0), (3, 1.0)],
    )
    held = util.geom_mean_na([4.0, 1.0])
    jumped = util.geom_mean_na([8.0, 1.0])
    _assert_summary(
        [slow, fast],
        [(rev, held) for rev in range(4)] + [(4, jumped), (5, jumped)],
    )

    slow = _machine('slow', [(40, 4.0), (10, 4.0)])
    fast = _machine('fast', [(30, 1.0), (10, 1.0), (40, 1.0), (20, 1.0)])
    _assert_summary(
        [slow, fast],
        [(10, held), (20, held), (30, held), (40, held)],
    )


def test_summary_zero_sample_is_not_repeated():
    # One 0 makes the geometric mean 0. Repeating it would hold the summary
    # at 0 on every later commit, so the gaps after it stay missing.
    blue = _machine('blue', [(0, 0.0)])
    purple = _machine('purple', [(rev, 2.0) for rev in range(4)])
    _assert_summary([blue, purple], [(0, 0.0), (1, 2.0), (2, 2.0), (3, 2.0)])

    # A 0 after a real sample does not bring the earlier value back.
    blue = _machine('blue', [(0, 4.0), (1, 0.0)])
    purple = _machine('purple', [(rev, 2.0) for rev in range(5)])
    _assert_summary(
        [blue, purple],
        [(0, util.geom_mean_na([4.0, 2.0])), (1, 0.0), (2, 2.0), (3, 2.0), (4, 2.0)],
    )


def test__combine_graph_data():
    g1 = Graph('1', {})
    g2 = Graph('2', {})
    g3 = Graph('3', {})
    for i in range(5):
        if i >= 3:
            g1.add_data_point(i, None)
        g2.add_data_point(i, i)
        if i <= 2:
            g3.add_data_point(i, [-i, -2 * i])

    x, ys = _combine_graph_data([g1, g2, g3])
    assert x == [0, 1, 2, 3, 4]
    assert ys == [
        [None, None, None, None, None],
        [0, 1, 2, 3, 4],
        [0, -1, -2, None, None],
        [0, -2, -4, None, None],
    ]


def test_graph_steps():
    vals = [
        (1, 1),
        (5, 1),
        (6, 1),
        (7, 1),
        (8, 1),
        (11, 2),
        (15, 2),
        (16, 2 + 1e-5),
        (17, 2),
        (18, 2),
    ]

    g = Graph('foo', {})
    for x, y in vals:
        g.add_data_point(x, y)

    steps = g.get_steps()
    lastval = steps[1][4]
    assert abs(lastval - 1e-5 / 5.0) < 1e-10
    assert steps == [(1, 8 + 1, 1.0, 1.0, 0), (11, 18 + 1, 2.0, 2.0, lastval)]

    multi_g = Graph('foo', {})
    for x, y in vals:
        multi_g.add_data_point(x, [y, y, y])

    for s in multi_g.get_steps():
        assert s == steps


def test_graph_filename_sanitization():
    g = Graph('hello:world', {'a/a': 'b>b', 'c*c': 'd\0\0d'})
    assert g.path == os.path.join('graphs', 'a_a-b_b', 'c_c-d__d', 'hello_world')


def _sgn(x):
    return 1 if x >= 0 else -1
