import os
import functools

try:
    import coverage as coverage_mod
except ImportError:
    coverage_mod = None

try:
    import mock
except ImportError:
    from unittest import mock

try:
    from zstacklib.test.utils import env
    from zstacklib.utils import debug
    from kvmagent.plugins.imagestore import ImageStoreClient
    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False


class PytestExtension(object):
    """Base class for integration test cases.

    Formerly used os._exit() to signal pass/fail to ztest.
    Now lets pytest handle process lifecycle normally.
    """

    cov = None

    @staticmethod
    def start_coverage():
        if coverage_mod is None or not _HAS_DEPS:
            return
        if not env.COVERAGE:
            return

        PytestExtension.cov = coverage_mod.Coverage(
            config_file=os.path.join(env.ZSTACK_UTILITY_SOURCE_DIR, '.coveragerc')
        )
        PytestExtension.cov.start()

    @staticmethod
    def stop_coverage():
        if PytestExtension.cov is None:
            return
        PytestExtension.cov.stop()
        PytestExtension.cov.save()

    @staticmethod
    def setup_modules_mock():
        if not _HAS_DEPS:
            return
        modules_to_mock = {
            ImageStoreClient: {
                'stop_mirror': None,
                'query_mirror_volumes': None,
                'mirror_volume': None,
            }
        }

        for k, v in modules_to_mock.items():
            for m, r in v.items():
                p = mock.patch.object(k, m, return_value=r)
                p.start()

    def setup_class(self):
        self.start_coverage()
        self.setup_modules_mock()

    def teardown_class(self):
        self.stop_coverage()
        # No longer calls os._exit() — pytest controls the process lifecycle


def ztest_decorater(func):
    """Decorator formerly used to track pass/fail for ztest.

    Now simplified to a pass-through — pytest handles test result collection.
    Kept for backwards compatibility so existing test files don't need changes.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper
