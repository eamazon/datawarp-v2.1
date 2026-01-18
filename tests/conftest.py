"""
Pytest configuration for DataWarp e2e tests.
"""
import pytest


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--force", action="store_true", default=False,
        help="Force reload data even if already loaded"
    )


@pytest.fixture
def force_reload(request):
    """Get force reload option from command line."""
    return request.config.getoption("--force")
