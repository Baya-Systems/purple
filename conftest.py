
def pytest_addoption(parser):
    parser.addoption("--quick", action="store", default=False, help="Skip slow parts of tests")
