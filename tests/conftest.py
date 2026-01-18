"""
Pytest configuration for DataWarp e2e tests.

Provides:
- --force option for reloading data
- Consolidated summary report at end of test run
- Machine-parseable output for agentic use
"""
import pytest
from collections import defaultdict
from datetime import datetime


# Global storage for test results (used by summary hook)
_test_results = defaultdict(lambda: {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "evidence": {}
})


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


@pytest.fixture
def record_evidence(request):
    """Fixture to record evidence for summary report."""
    pub_code = None

    # Extract publication code from test parameters
    if hasattr(request, 'node') and hasattr(request.node, 'callspec'):
        params = request.node.callspec.params
        pub_code = params.get('pub_code')

    def _record(key: str, value):
        if pub_code:
            _test_results[pub_code]["evidence"][key] = value

    return _record


def pytest_runtest_logreport(report):
    """Track test results per publication."""
    if report.when == "call":
        # Extract publication from test name like "test_xxx[adhd]"
        if "[" in report.nodeid and "]" in report.nodeid:
            pub = report.nodeid.split("[")[-1].rstrip("]")
            if report.passed:
                _test_results[pub]["passed"] += 1
            elif report.failed:
                _test_results[pub]["failed"] += 1
            elif report.skipped:
                _test_results[pub]["skipped"] += 1


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print consolidated summary report at end of test run."""
    if not _test_results:
        return

    # Only show summary if we ran publication tests
    terminalreporter.write_sep("=", "E2E PUBLICATION SUMMARY")
    terminalreporter.write_line("")

    # Header
    terminalreporter.write_line(f"{'PUBLICATION':<35} {'PASSED':>8} {'FAILED':>8} {'SKIPPED':>8} {'STATUS':>10}")
    terminalreporter.write_line("-" * 75)

    total_passed = 0
    total_failed = 0
    total_skipped = 0

    for pub, results in sorted(_test_results.items()):
        passed = results["passed"]
        failed = results["failed"]
        skipped = results["skipped"]

        total_passed += passed
        total_failed += failed
        total_skipped += skipped

        if failed > 0:
            status = "❌ FAIL"
        elif skipped > 0 and passed == 0:
            status = "⏭️  SKIP"
        else:
            status = "✅ PASS"

        terminalreporter.write_line(f"{pub:<35} {passed:>8} {failed:>8} {skipped:>8} {status:>10}")

    terminalreporter.write_line("-" * 75)
    terminalreporter.write_line(f"{'TOTAL':<35} {total_passed:>8} {total_failed:>8} {total_skipped:>8}")
    terminalreporter.write_line("")

    # Machine-parseable summary (for agents)
    terminalreporter.write_sep("-", "MACHINE-PARSEABLE SUMMARY")
    terminalreporter.write_line("")
    terminalreporter.write_line(f"SUMMARY: publications={len(_test_results)} passed={total_passed} failed={total_failed} skipped={total_skipped}")

    for pub, results in sorted(_test_results.items()):
        status = "PASS" if results["failed"] == 0 else "FAIL"
        terminalreporter.write_line(f"PUB:{pub} status={status} passed={results['passed']} failed={results['failed']}")

    terminalreporter.write_line("")

    # Clear for next run
    _test_results.clear()
