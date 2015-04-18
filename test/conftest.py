
def pytest_addoption(parser):
    selenium_class_names = ("Android", "Chrome", "Firefox", "Ie", "Opera", "PhantomJS", "Remote", "Safari")
    parser.addoption("--webdriver", action="store", choices=selenium_class_names,
                     default="PhantomJS",
                     help="Selenium WebDriver interface to use for running the test. Default: PhantomJS")
    parser.addoption("--webdriver-options", action="store", default="{}",
                     help="Python dictionary of options to pass to the Selenium WebDriver class. Default: {}")
