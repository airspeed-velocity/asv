# Licensed under a 3-clause BSD style license - see LICENSE.rst
from asv.config import Config
from asv.commands.publish import GRAPH_UI_RESERVED_PARAMS


def test_reserved_matrix_keys_constant():
    assert 'benchmark' in Config.GRAPH_UI_RESERVED_MATRIX_KEYS
    assert 'benchmark' in GRAPH_UI_RESERVED_PARAMS


def test_config_loads_with_benchmark_matrix_key():
    conf = Config.from_json({
        'repo': '.',
        'project': 'x',
        'matrix': {'benchmark': ['1.4.1'], 'numpy': []},
    })
    assert 'benchmark' in conf.matrix
