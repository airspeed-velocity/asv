import os
import shutil
import contextlib
import pytest
from os.path import join, abspath, dirname
from asv import config
from asv import repo
from .test_workflow import generate_basic_conf
from .tools import locked_cache_dir, run_asv_with_conf
from asv.repo import get_repo
from .test_benchmarks import ASV_CONF_JSON, BENCHMARK_DIR
from asv import environment
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


@pytest.fixture
def benchmarks_fixture(tmpdir):
    tmpdir = str(tmpdir)
    os.chdir(tmpdir)

    shutil.copytree(BENCHMARK_DIR, 'benchmark')

    d = {}
    d.update(ASV_CONF_JSON)
    d['env_dir'] = "env"
    d['benchmark_dir'] = 'benchmark'
    d['repo'] = tools.generate_test_repo(tmpdir, [0]).path
    d['branches'] = ["master"]
    conf = config.Config.from_json(d)

    repo = get_repo(conf)
    envs = list(environment.get_environments(conf, None))
    commit_hash = repo.get_hash_from_name(repo.get_branch_name())

    return conf, repo, envs, commit_hash


@pytest.fixture(scope="session")
def basic_html(request):
    with locked_cache_dir(request.config, "asv-test_web-basic_html", timeout=900) as cache_dir:
        tmpdir = join(str(cache_dir), 'cached')
        html_dir, dvcs = _rebuild_basic_html(tmpdir)
        return html_dir, dvcs
