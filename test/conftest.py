import os
import shutil
import contextlib
import pytest
import selenium
import textwrap
from os.path import join, abspath, dirname
from asv import config
from asv import repo
from .test_workflow import generate_basic_conf
from .tools import (locked_cache_dir, run_asv_with_conf, _build_dummy_wheels,
                    WAIT_TIME, DUMMY1_VERSION, DUMMY2_VERSIONS, WIN, HAS_CONDA,
                    PYTHON_VER1, PYTHON_VER2)
from .test_web import _rebuild_basic_html


try:
    import hglib
except ImportError:
    hglib = None

from . import tools


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


@pytest.fixture(params=[
    "git",
    pytest.param("hg", marks=pytest.mark.skipif(hglib is None, reason="needs hglib")),
])
def two_branch_repo_case(request, tmpdir):
    r"""
    This test ensure we follow the first parent in case of merges

    The revision graph looks like this:

        @  Revision 6 (default)
        |
        | o  Revision 5 (stable)
        | |
        | o  Merge master
        |/|
        o |  Revision 4
        | |
        o |  Merge stable
        |\|
        o |  Revision 3
        | |
        | o  Revision 2
        |/
        o  Revision 1

    """
    dvcs_type = request.param
    tmpdir = str(tmpdir)
    if dvcs_type == "git":
        master = "master"
    elif dvcs_type == "hg":
        master = "default"
    dvcs = tools.generate_repo_from_ops(tmpdir, dvcs_type, [
        ("commit", 1),
        ("checkout", "stable", master),
        ("commit", 2),
        ("checkout", master),
        ("commit", 3),
        ("merge", "stable"),
        ("commit", 4),
        ("checkout", "stable"),
        ("merge", master, "Merge master"),
        ("commit", 5),
        ("checkout", master),
        ("commit", 6),
    ])

    conf = config.Config()
    conf.branches = [master, "stable"]
    conf.repo = dvcs.path
    conf.project = join(tmpdir, "repo")
    r = repo.get_repo(conf)
    return dvcs, master, r, conf


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

@pytest.fixture(scope="session")
def basic_html(request):
    with locked_cache_dir(request.config, "asv-test_web-basic_html", timeout=900) as cache_dir:
        tmpdir = join(str(cache_dir), 'cached')
        html_dir, dvcs = _rebuild_basic_html(tmpdir)
        return html_dir, dvcs
