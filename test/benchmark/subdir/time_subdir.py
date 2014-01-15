import time

x = None


def time_foo():
    if x != 42:
        raise RuntimeError()
    time.sleep(0.01)


def setup_foo():
    global x
    x = 42


time_foo.setup = setup_foo
