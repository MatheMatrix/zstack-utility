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


# Detect if running inside ztest nested VM (zguest) or local pytest
_IN_ZTEST = os.path.exists('/root/.zguest') or os.environ.get('ZTEST_MODE') == '1'

Out_flag = True


class PytestExtension(object):
    """Base class for ztest integration test cases.

    In ztest mode: uses os._exit(0/1) to signal pass/fail to ztest framework.
    In local pytest mode: lets pytest handle process lifecycle normally.
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

        for k, v in list(modules_to_mock.items()):
            for m, r in list(v.items()):
                p = mock.patch.object(k, m, return_value=r)
                p.start()

    def setup_class(self):
        self.start_coverage()
        self.setup_modules_mock()

    def teardown_class(self):
        self.stop_coverage()

        if _IN_ZTEST:
            if Out_flag:
                os._exit(0)
            os._exit(1)


def ztest_decorater(func):
    """Decorator that tracks pass/fail for ztest framework.

    In ztest mode: sets Out_flag so teardown_class knows the result.
    In local pytest mode: pass-through, pytest handles results.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        global Out_flag
        if _IN_ZTEST:
            last_out_flag = Out_flag
            Out_flag = False
            func(*args, **kwargs)
            Out_flag = last_out_flag
        else:
            return func(*args, **kwargs)

    return wrapper
