import os
import contextlib
from . import tools
import pytest
from .test_workflow import generate_basic_conf
from asv import config


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


@pytest.fixture
def basic_conf(tmpdir, dummy_packages):
    return generate_basic_conf(tmpdir)

@pytest.fixture
def show_fixture(tmpdir, example_results):
    tmpdir = str(tmpdir)
    os.chdir(tmpdir)

    conf = config.Config.from_json(
        {'results_dir': example_results,
         'repo': tools.generate_test_repo(tmpdir).path,
         'project': 'asv',
         'environment_type': "shouldn't matter what"})

    return conf


@pytest.fixture
def basic_conf(tmpdir, dummy_packages):
    return generate_basic_conf(tmpdir)


@pytest.fixture
def basic_conf_with_subdir(tmpdir, dummy_packages):
    return generate_basic_conf(tmpdir, 'some_subdir')


@pytest.fixture
def existing_env_conf(tmpdir):
    tmpdir, local, conf, machine_file = generate_basic_conf(tmpdir)
    conf.environment_type = "existing"
    conf.pythons = ["same"]
    return tmpdir, local, conf, machine_file




