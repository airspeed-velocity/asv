import os
import contextlib
from os.path import abspath, join, dirname
from .tools import WIN, run_asv_with_conf
import pytest
from asv import config
import shutil
import selenium
import textwrap
from .tools import (WAIT_TIME, locked_cache_dir, DUMMY1_VERSION,
                    DUMMY2_VERSIONS, HAS_CONDA, PYTHON_VER2, PYTHON_VER1,
                    _build_dummy_wheels)


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


@pytest.fixture(scope="session")
def browser(request, pytestconfig):
    """
    Fixture for Selenium WebDriver browser interface
    """
    driver_str = pytestconfig.getoption('webdriver')

    if driver_str == "None":
        pytest.skip("No webdriver selected for tests (use --webdriver).")

    # Evaluate the options
    def FirefoxHeadless():
        options = selenium.webdriver.FirefoxOptions()
        options.add_argument("-headless")
        return selenium.webdriver.Firefox(options=options)

    def ChromeHeadless():
        options = selenium.webdriver.ChromeOptions()
        options.add_argument('headless')
        options.add_experimental_option('w3c', False)
        return selenium.webdriver.Chrome(options=options)

    ns = {}
    exec("import selenium.webdriver", ns)
    exec("from selenium.webdriver import *", ns)
    ns['FirefoxHeadless'] = FirefoxHeadless
    ns['ChromeHeadless'] = ChromeHeadless

    create_driver = ns.get(driver_str, None)
    if create_driver is None:
        src = "def create_driver():\n"
        src += textwrap.indent(driver_str, "    ")
        exec(src, ns)
        create_driver = ns['create_driver']

    # Create the browser
    browser = create_driver()

    # Set timeouts
    browser.set_page_load_timeout(WAIT_TIME)
    browser.set_script_timeout(WAIT_TIME)

    # Clean up on fixture finalization
    def fin():
        browser.quit()
    request.addfinalizer(fin)

    # Set default time to wait for AJAX requests to complete
    browser.implicitly_wait(WAIT_TIME)

    return browser


@pytest.fixture
def dummy_packages(request, monkeypatch):
    """
    Build dummy wheels for required packages and set PIP_FIND_LINKS + CONDARC
    """
    to_build = [('asv_dummy_test_package_1', DUMMY1_VERSION)]
    to_build += [('asv_dummy_test_package_2', ver) for ver in DUMMY2_VERSIONS]

    tag = [PYTHON_VER1, PYTHON_VER2, to_build, HAS_CONDA]

    with locked_cache_dir(request.config, "asv-wheels", timeout=900, tag=tag) as cache_dir:
        wheel_dir = os.path.abspath(join(str(cache_dir), 'wheels'))

        monkeypatch.setenv(str('PIP_FIND_LINKS'), str('file://' + wheel_dir))

        condarc = join(wheel_dir, 'condarc')
        monkeypatch.setenv(str('CONDARC'), str(condarc))

        if os.path.isdir(wheel_dir):
            return

        tmpdir = join(str(cache_dir), "tmp")
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)
        os.makedirs(tmpdir)

        try:
            os.makedirs(wheel_dir)
            _build_dummy_wheels(tmpdir, wheel_dir, to_build, build_conda=HAS_CONDA)
        except Exception:
            shutil.rmtree(wheel_dir)
            raise

        # Conda packages were installed in a local channel
        if not WIN:
            wheel_dir_str = "file://{0}".format(wheel_dir)
        else:
            wheel_dir_str = wheel_dir

        with open(condarc, 'w') as f:
            f.write("channels:\n"
                    "- defaults\n"
                    "- {0}".format(wheel_dir_str))
