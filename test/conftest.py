import os
import contextlib
from os.path import abspath, join, dirname
from .tools import run_asv_with_conf
import pytest
from asv import config
import shutil
from .tools import locked_cache_dir


def pytest_addoption(parser):
    parser.addoption("--webdriver", action="store", default="None",
                     help=("Selenium WebDriver interface to use for running the test. "
                           "Choices: None, PhantomJS, Chrome, Firefox, ChromeHeadless, "
                           "FirefoxHeadless. Alternatively, it can be arbitrary Python code "
                           "with a return statement with selenium.webdriver object, for "
                           "example 'return Chrome()'"))

    parser.addoption("--environment-type", action="store", default=None,
                     choices=("conda", "virtualenv"),
                     help="environment_type to use in tests by default")


def pytest_sessionstart(session):
    os.environ['PIP_NO_INDEX'] = '1'
    _monkeypatch_conda_lock(session.config)

    # Unregister unwanted environment types
    env_type = session.config.getoption('environment_type')
    if env_type is not None:
        import asv.environment
        import asv.util

        for cls in asv.util.iter_subclasses(asv.environment.Environment):
            cls.matches_python_fallback = (cls.tool_name in (env_type, "existing"))


def _monkeypatch_conda_lock(config):
    import asv.plugins.conda
    import asv.util
    import filelock

    @contextlib.contextmanager
    def _conda_lock():
        conda_lock = asv.util.get_multiprocessing_lock("conda_lock")
        with conda_lock, filelock.FileLock(str(path)):
            yield

    path = config.cache.makedir('conda-lock') / 'lock'
    asv.plugins.conda._conda_lock = _conda_lock


@pytest.fixture(scope="session")
def example_results(request):
    with locked_cache_dir(request.config, "example-results") as cache_dir:
        src = abspath(join(dirname(__file__), 'example_results'))
        dst = abspath(join(cache_dir, 'results'))

        if os.path.isdir(dst):
            return dst

        shutil.copytree(src, dst)

        src_machine = join(dirname(__file__), 'asv-machine.json')
        dst_machine = join(cache_dir, 'asv-machine.json')
        shutil.copyfile(src_machine, dst_machine)

        # Convert to current file format
        conf = config.Config.from_json({'results_dir': dst,
                                        'repo': 'none',
                                        'project': 'asv'})
        run_asv_with_conf(conf, 'update', _machine_file=dst_machine)

        return dst
