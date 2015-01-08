import asvtools


types = [
    ('process_time', 'time'),
    ('wall_time', 'time', {'timer': asvtools.wall_time, 'repeat': 30}),
    ('memory', 'mem')
]


def multi_bench():
    range(1000)
multi_bench.types = types


class MySuite:
    types = types

    def multi_range(self):
        range(1000)

    def multi_for_loop(self):
        x = 0
        for i in range(1000):
            x *= i
