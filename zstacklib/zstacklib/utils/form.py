from zstacklib.utils import log

logger = log.get_logger(__name__)


def _load(stdout, sep=None):
    # type: (str, str) -> list[dict]
    ret = []

    if not stdout:
        return ret

    lines = stdout.splitlines()
    lines = [line.strip() for line in lines if line.strip()]
    if len(lines) < 2:
        return ret

    if sep == ' ':
        sep = None

    heads = [h.strip() for h in lines[0].split(sep)]
    for l in lines[1:]:
        o = {}
        for h in heads:
            o[h] = None
        values = l.split(sep)
        for i, v in enumerate(values):
            val = v.strip()
            if sep is not None and val == '':
                val = None
            o[heads[i]] = val
        ret.append(o)

    return ret


def load(stdout, sep=None):
    try:
        return _load(stdout, sep)
    except Exception as e:
        logger.debug("not a standard form:%s" % e.message)
        return []
