import os


def pytest_addoption(parser):
    parser.addoption("--webdriver", action="store", default="None",
                     help=("Selenium WebDriver interface to use for running the test. "
                           "Choices: None, PhantomJS, Chrome, Firefox, ChromeHeadless, "
                           "FirefoxHeadless. Alternatively, it can be arbitrary Python code "
                           "with a return statement with selenium.webdriver object, for "
                           "example 'return Chrome()'"))

    parser.addoption("--offline", action="store_true", default=False,
                     help=("Do not download items from internet. Use if you have predownloaded "
                           "packages and set PIP_FIND_LINKS."))


def pytest_sessionstart(session):
    if session.config.getoption('offline'):
        os.environ['PIP_NO_INDEX'] = '1'
        os.environ['CONDA_OFFLINE'] = 'True'
