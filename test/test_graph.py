from asv.graph import Graph


def test_graph_single():
    vals = [
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
        (5, 5),
        (6, None)
    ]

    # Should give same data back, excluding missing values at edges
    g = Graph('foo', {}, {})
    for k, v in vals:
        g.add_data_point(k, v)
    data = g.get_data()
    assert data == vals[:-1]

    # Should average duplicate values
    g = Graph('foo', {}, {})
    g.add_data_point(4, 3)
    for k, v in vals:
        g.add_data_point(k, v)
    g.add_data_point(4, 5)
    data = g.get_data()
    assert data[3][0] == 4
    assert abs(data[3][1] - (3 + 4 + 5)/3.) < 1e-10

    # Summary graph should be the same as the main graph
    g = Graph('foo', {}, {}, summary=True)
    for k, v in vals:
        g.add_data_point(k, v)
    data = g.get_data()
    assert len(data) == len(vals) - 1
    for v, d in zip(vals, data):
        kv, xv = v
        kd, xd = d
        assert kv == kd
        assert abs(xv - xd) < 1e-10


def test_graph_multi():
    vals = [
        (0, [None, None, None]),
        (1, [1, None, None]),
        (2, [2,    5, 4]),
        (3, [3,    4, -60]),
        (4, [4,    3, 2]),
        (5, [None, 2, None]),
        (6, [6,    1, None])
    ]

    filled_vals = [
        (1, [1, 5, 4]),
        (2, [2, 5, 4]),
        (3, [3, 4, -60]),
        (4, [4, 3, 2]),
        (5, [4, 2, 2]),
        (6, [6, 1, 2])
    ]

    # Should give same data back, with missing data at edges removed
    g = Graph('foo', {}, {})
    for k, v in vals:
        g.add_data_point(k, v)
    data = g.get_data()
    assert data == vals[1:]

    # Should average duplicate values
    g = Graph('foo', {}, {})
    g.add_data_point(4, [1, 2, 3])
    for k, v in vals:
        g.add_data_point(k, v)
    g.add_data_point(4, [3, 2, 1])
    data = g.get_data()
    assert data[3][0] == 4
    assert abs(data[3][1][0] - (1 + 4 + 3)/3.) < 1e-10
    assert abs(data[3][1][1] - (2 + 3 + 2)/3.) < 1e-10
    assert abs(data[3][1][2] - (3 + 2 + 1)/3.) < 1e-10

    # The summary graph is obtained by geometric mean of filled data
    g = Graph('foo', {}, {}, summary=True)
    for k, v in vals:
        g.add_data_point(k, v)
    data = g.get_data()

    for v, d in zip(filled_vals, data):
        kv, xvs = v
        kd, xd = d
        assert kv == kd

        # geom mean, with some sign convention
        expected = _sgn(sum(xvs)) * (abs(xvs[0]*xvs[1]*xvs[2]))**(1./3)
        assert abs(xd - expected) < 1e-10


def test_empty_graph():
    g = Graph('foo', {}, {})
    g.add_data_point(1, None)
    g.add_data_point(2, None)
    g.add_data_point(3, None)
    data = g.get_data()
    assert data == []


    g = Graph('foo', {}, {})
    g.add_data_point(1, None)
    g.add_data_point(1, [None, None])
    g.add_data_point(2, [None, None])
    g.add_data_point(3, None)
    g.add_data_point(4, [None, None])
    data = g.get_data()
    assert data == []


def _sgn(x):
    return 1 if x >= 0 else -1
