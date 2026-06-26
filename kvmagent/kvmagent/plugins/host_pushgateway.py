import glob
import re


DEFAULT_HOST_PUSHGATEWAY_AUTH_HEADER = "Basic YWRtaW46enN0YWNrQDEyMw=="
LIGHTTPD_CONF_GLOBS = [
    "/var/lib/zstack/userdata/*/lighttpd.conf",
    "/var/lib/zstack/tf_userdata/lighttpd.conf",
]
AUTH_HEADER_PATTERN = re.compile(r'Authorization"\s*=>\s*"([^"]+)"')


def get_auth_header(conf_paths=None):
    if conf_paths is None:
        conf_paths = []
        for pattern in LIGHTTPD_CONF_GLOBS:
            conf_paths.extend(glob.glob(pattern))

    for conf_path in conf_paths:
        try:
            with open(conf_path, "r") as fd:
                match = AUTH_HEADER_PATTERN.search(fd.read())
                if match:
                    return match.group(1)
        except Exception:
            pass

    return DEFAULT_HOST_PUSHGATEWAY_AUTH_HEADER


def make_push_metrics_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": get_auth_header()
    }


def make_get_metrics_headers():
    return {
        "Content-Type": "text/plain",
        "Authorization": get_auth_header()
    }


def make_delete_metric_headers():
    return {
        "Authorization": get_auth_header()
    }
