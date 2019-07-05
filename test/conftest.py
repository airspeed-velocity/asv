import os
import contextlib


def pytest_addoption(parser):
    parser.addoption("--webdriver", action="store", default="None",
                     help=("Selenium WebDriver interface to use for running the test. "
                           "Choices: None, PhantomJS, Chrome, Firefox, ChromeHeadless, "
                           "FirefoxHeadless. Alternatively, it can be arbitrary Python code "
                           "with a return statement with selenium.webdriver object, for "
                           "example 'return Chrome()'"))


def pytest_sessionstart(session):
    os.environ['PIP_NO_INDEX'] = '1'

    if 'PYTEST_XDIST_WORKER' in os.environ:
        # Use interprocess locking for conda when pytest-xdist is active
        _monkeypatch_conda_lock(session.config)


def _monkeypatch_conda_lock(config):
    import asv.plugins.conda
    try:
        asv.plugins.conda._find_conda()
    except IOError:
        # No lock needed
        return

    import lockfile

    @contextlib.contextmanager
    def _conda_lock():
        with asv.plugins.conda._conda_main_lock, lockfile.LockFile(str(path)):
            yield

    path = config.cache.makedir('conda-lock') / 'lock'
    asv.plugins.conda._conda_lock = _conda_lock
