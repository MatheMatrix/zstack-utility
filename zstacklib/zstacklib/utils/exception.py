from contextlib import contextmanager
from zstacklib.utils import log

logger = log.get_logger(__name__)


@contextmanager
def ignore_exception(message, exception_type):
    try:
        yield
    except exception_type as ex:
        if message not in str(ex.message):
            raise ex
