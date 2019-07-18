import os
import contextlib


def pytest_addoption(parser):
    parser.addoption("--webdriver", action="store", default="None",
                     help=("Selenium WebDriver interface to use for running the test. "
                           "Choices: None, PhantomJS, Chrome, Firefox, ChromeHeadless, "
                           "FirefoxHeadless. Alternatively, it can be arbitrary Python code "
                           "with a return statement with selenium.webdriver object, for "
                           "example 'return Chrome()'"))

    parser.addoption("--sensible-test-order", action="store_true", default=False,
                     help=("Run tests in 'sensible' order."))


def pytest_sessionstart(session):
    os.environ['PIP_NO_INDEX'] = '1'
    _monkeypatch_conda_lock(session.config)


def _monkeypatch_conda_lock(config):
    import asv.plugins.conda
    import asv.util
    import lockfile

    @contextlib.contextmanager
    def _conda_lock():
        conda_lock = asv.util.get_multiprocessing_lock("conda_lock")
        with conda_lock, lockfile.LockFile(str(path)):
            yield

    path = config.cache.makedir('conda-lock') / 'lock'
    asv.plugins.conda._conda_lock = _conda_lock


def pytest_collection_modifyitems(session, config, items):
    """
    Reorder tests so that slow fixtures are initialized first
    """
    if not config.getoption('sensible_test_order'):
        return

    order = [
        "test_workflow.py::test_run_publish",
    ]

    def sorter(item):
        for j, name in enumerate(order):
            if item.nodeid.endswith(name):
                return -j-1
        return 0

    items.sort(key=sorter)
