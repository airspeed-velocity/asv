import asvtools


types = [
    ('process_time', 'time'),
    ('wall_time', 'time', {'timer': asvtools.wall_time, 'repeat': 30}),
    ('memory', 'mem')
]


def multi_bench():
    range(100)
multi_bench.types = types


class MySuite:
    types = types

    def multi_range(self):
        range(100000)

    def multi_xrange(self):
        xrange(100000)
